#include "A6Journal.hpp"
#include "Files.hpp"

#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QMessageAuthenticationCode>
#include <QRegularExpression>

#ifdef Q_OS_WIN
#include <qt_windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace convergence {
namespace {

constexpr qsizetype maximumJournalSize = 64 * 1024 * 1024;
constexpr qsizetype maximumEventSize = 2 * 1024 * 1024;
constexpr auto eventSchema = "v3.a6.journal_event/1";

void verifyTrustedPath(QDir dir)
{
    require(dir.isAbsolute() && dir.canonicalPath() == dir.absolutePath(), "A6_TRUST_DIRECTORY_REDIRECTED");
    do {
        const QFileInfo part(dir.absolutePath());
        require(!part.isSymLink() && !part.isJunction(), "A6_TRUST_DIRECTORY_REDIRECTED");
#ifdef Q_OS_WIN
        const auto path = QDir::toNativeSeparators(dir.absolutePath()).toStdWString();
        const auto attributes = GetFileAttributesW(path.c_str());
        require(attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_REPARSE_POINT),
                "A6_TRUST_DIRECTORY_REDIRECTED");
#endif
    } while (!dir.isRoot() && dir.cdUp());
}

QString checkedSha(const QJsonValue &value)
{
    static const QRegularExpression syntax(QStringLiteral("\\A[0-9a-f]{64}\\z"));
    const auto sha = value.toString();
    require(syntax.match(sha).hasMatch(), "A6_JOURNAL_INVALID_DIGEST");
    return sha;
}

QByteArray macFor(const QByteArray &key, const QByteArray &payload)
{
    return QMessageAuthenticationCode::hash(payload, key, QCryptographicHash::Sha256).toHex();
}

bool equalMac(const QByteArray &given, const QByteArray &computed)
{
    if (given.size() != computed.size())
        return false;
    unsigned int difference = 0;
    for (qsizetype i = 0; i < given.size(); ++i)
        difference |= static_cast<unsigned char>(given.at(i)) ^ static_cast<unsigned char>(computed.at(i));
    return difference == 0;
}

QDateTime eventTime(const QJsonValue &value)
{
    const auto text = value.toString();
    const auto time = QDateTime::fromString(text, Qt::ISODateWithMs);
    require(time.isValid() && text.endsWith('Z') && time.toUTC().toString(Qt::ISODateWithMs) == text,
            "A6_JOURNAL_INVALID_TIME");
    return time.toUTC();
}

bool terminal(const QString &state)
{
    return state == "COMMITTED_PRIVATE" || state == "ABORTED" || state == "QUARANTINED";
}

bool advances(const QString &previous, const QString &next)
{
    if (previous.isEmpty())
        return next == "REQUESTED";
    if (terminal(previous))
        return false;
    if (next == "ABORTED" || next == "QUARANTINED")
        return true;
    static const QMap<QString, QString> successor{
        {"REQUESTED", "AUTHORIZED_RESERVED"}, {"AUTHORIZED_RESERVED", "BUILDING_PRIVATE"},
        {"BUILDING_PRIVATE", "BUILT"}, {"BUILT", "INDEPENDENTLY_VALIDATED"},
        {"INDEPENDENTLY_VALIDATED", "COMMITTED_PRIVATE"}};
    return successor.value(previous) == next && !next.isEmpty();
}

QString prefixDigest(const QJsonArray &events, qsizetype count)
{
    QJsonArray prefix;
    for (qsizetype i = 0; i < count; ++i)
        prefix.append(events.at(i));
    return digest(QJsonDocument(prefix).toJson(QJsonDocument::Compact));
}

} // namespace

class A6Journal::File final {
public:
    File(const QString &path, bool writable) : name_(path)
    {
#ifdef Q_OS_WIN
        const auto native = QDir::toNativeSeparators(path).toStdWString();
        handle_ = CreateFileW(native.c_str(), writable ? GENERIC_READ | GENERIC_WRITE : GENERIC_READ,
                              FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        const auto error = handle_ == INVALID_HANDLE_VALUE ? GetLastError() : ERROR_SUCCESS;
        require(error != ERROR_SHARING_VIOLATION, "AUTHORITY_STATE_BUSY");
        require(handle_ != INVALID_HANDLE_VALUE, "A6_JOURNAL_NOT_PROVISIONED_OR_INACCESSIBLE");
#else
        const auto native = QFile::encodeName(path);
        handle_ = ::open(native.constData(), (writable ? O_RDWR | O_APPEND : O_RDONLY) | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
        require(handle_ >= 0, "A6_JOURNAL_NOT_PROVISIONED_OR_INACCESSIBLE");
#endif
        try {
#ifndef Q_OS_WIN
            require(!writable || ::flock(handle_, LOCK_EX | LOCK_NB) == 0, "AUTHORITY_STATE_BUSY");
#endif
            checkIdentity();
        } catch (...) {
            close();
            throw;
        }
    }

    ~File() { close(); }

    QByteArray readAll(qsizetype limit) const
    {
        checkIdentity();
        QByteArray bytes;
#ifdef Q_OS_WIN
        LARGE_INTEGER size{};
        LARGE_INTEGER start{};
        require(GetFileSizeEx(handle_, &size) && size.QuadPart >= 0 && size.QuadPart <= limit &&
                SetFilePointerEx(handle_, start, nullptr, FILE_BEGIN), "A6_JOURNAL_INVALID_FILE_SIZE");
        bytes.resize(static_cast<qsizetype>(size.QuadPart));
        DWORD readCount = 0;
        require(ReadFile(handle_, bytes.data(), static_cast<DWORD>(bytes.size()), &readCount, nullptr) &&
                readCount == static_cast<DWORD>(bytes.size()), "A6_JOURNAL_READ_FAILED");
#else
        struct stat info{};
        require(::fstat(handle_, &info) == 0 && info.st_size >= 0 && info.st_size <= limit &&
                ::lseek(handle_, 0, SEEK_SET) == 0, "A6_JOURNAL_INVALID_FILE_SIZE");
        bytes.resize(static_cast<qsizetype>(info.st_size));
        qsizetype offset = 0;
        while (offset < bytes.size()) {
            const auto count = ::read(handle_, bytes.data() + offset, static_cast<size_t>(bytes.size() - offset));
            if (count < 0 && errno == EINTR)
                continue;
            require(count > 0, "A6_JOURNAL_READ_FAILED");
            offset += count;
        }
#endif
        return bytes;
    }

    void append(const QByteArray &bytes)
    {
        checkIdentity();
#ifdef Q_OS_WIN
        LARGE_INTEGER size{};
        LARGE_INTEGER end{};
        require(GetFileSizeEx(handle_, &size) && size.QuadPart <= maximumJournalSize - bytes.size() &&
                SetFilePointerEx(handle_, end, nullptr, FILE_END), "A6_JOURNAL_APPEND_POSITION_FAILED");
        DWORD count = 0;
        require(WriteFile(handle_, bytes.constData(), static_cast<DWORD>(bytes.size()), &count, nullptr) &&
                count == static_cast<DWORD>(bytes.size()) && FlushFileBuffers(handle_), "A6_JOURNAL_DURABILITY_UNCERTAIN");
#else
        struct stat info{};
        require(::fstat(handle_, &info) == 0 && info.st_size <= maximumJournalSize - bytes.size(), "A6_JOURNAL_APPEND_POSITION_FAILED");
        qsizetype offset = 0;
        while (offset < bytes.size()) {
            const auto count = ::write(handle_, bytes.constData() + offset, static_cast<size_t>(bytes.size() - offset));
            if (count < 0 && errno == EINTR)
                continue;
            require(count > 0, "A6_JOURNAL_DURABILITY_UNCERTAIN");
            offset += count;
        }
        int result = 0;
        do {
            result = ::fsync(handle_);
        } while (result < 0 && errno == EINTR);
        require(result == 0, "A6_JOURNAL_DURABILITY_UNCERTAIN");
#endif
        checkIdentity();
    }

private:
    void checkIdentity() const
    {
#ifdef Q_OS_WIN
        BY_HANDLE_FILE_INFORMATION info{};
        require(GetFileType(handle_) == FILE_TYPE_DISK && GetFileInformationByHandle(handle_, &info) &&
                !(info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)) &&
                info.nNumberOfLinks == 1, "A6_JOURNAL_FILE_REDIRECTED_OR_SHARED");
#else
        struct stat info{};
        struct stat current{};
        const auto native = QFile::encodeName(name_);
        require(::fstat(handle_, &info) == 0 && S_ISREG(info.st_mode) && info.st_nlink == 1 &&
                ::lstat(native.constData(), &current) == 0 && current.st_dev == info.st_dev && current.st_ino == info.st_ino,
                "A6_JOURNAL_FILE_REDIRECTED_OR_SHARED");
#endif
    }

    void close()
    {
#ifdef Q_OS_WIN
        CloseHandle(handle_);
#else
        ::close(handle_);
#endif
    }

    QString name_;
#ifdef Q_OS_WIN
    HANDLE handle_ = INVALID_HANDLE_VALUE;
#else
    int handle_ = -1;
#endif
};

A6Journal::A6Journal(const QDir &trusted, const QString &keySha256, const QDateTime &observedAt) : trusted_(trusted)
{
    verifyTrustedPath(trusted_);
    const File keyFile(trusted_.filePath("a6-journal.key"), false);
    key_ = keyFile.readAll(32);
    require(key_.size() == 32 && digest(key_) == checkedSha(keySha256), "A6_JOURNAL_KEY_MISMATCH");
    file_ = std::make_unique<File>(trusted_.filePath("a6-journal.jsonl"), true);
    const auto history = file_->readAll(maximumJournalSize);
    require(history.endsWith('\n'), "A6_JOURNAL_EMPTY_OR_TORN");

    qsizetype beginning = 0;
    while (beginning < history.size()) {
        const auto end = history.indexOf('\n', beginning);
        require(end > beginning && end - beginning + 1 <= maximumEventSize, "A6_JOURNAL_INVALID_EVENT_SIZE");
        const auto envelope = parseUniqueObject(history.sliced(beginning, end - beginning), "A.6 journal envelope");
        require(envelope.keys() == QStringList{"event_b64", "mac"}, "A6_JOURNAL_INVALID_ENVELOPE");
        const auto encoded = envelope.value("event_b64").toString().toLatin1();
        const auto payload = QByteArray::fromBase64(encoded, QByteArray::AbortOnBase64DecodingErrors);
        const auto mac = checkedSha(envelope.value("mac")).toLatin1();
        require(!payload.isEmpty() && payload.toBase64() == encoded && equalMac(mac, macFor(key_, payload)),
                "A6_JOURNAL_AUTHENTICATION_FAILED");
        apply(parseUniqueObject(payload, "A.6 journal event"), mac);
        beginning = end + 1;
    }
    const auto interrupted = decisions_;
    for (auto it = interrupted.cbegin(); it != interrupted.cend(); ++it) {
        if (!terminal(it.value()))
            append("QUARANTINED", it.key(), {{"reason", "INTERRUPTED_TRANSACTION"}, {"previous_state", it.value()}}, observedAt);
    }
}

A6Journal::~A6Journal() = default;

void A6Journal::apply(const QJsonObject &event, const QByteArray &mac)
{
    require(event.keys() == QStringList{"at_utc", "decision_id", "detail", "previous_mac", "schema", "sequence", "state"} &&
            event.value("schema") == eventSchema && event.value("sequence").toInt(-1) == sequence_ &&
            event.value("previous_mac") == QString::fromLatin1(previousMac_) &&
            event.value("decision_id").isString() && event.value("detail").isObject(), "A6_JOURNAL_CHAIN_INVALID");
    const auto time = eventTime(event.value("at_utc"));
    require(!lastSeen_.isValid() || time >= lastSeen_, "CLOCK_ROLLBACK");
    const auto next = event.value("state").toString();
    const auto id = event.value("decision_id").toString();
    const auto detail = event.value("detail").toObject();
    if (sequence_ == 0) {
        require(next == "GENESIS" && id.isEmpty() && detail.isEmpty(), "A6_JOURNAL_GENESIS_REQUIRED");
        registryPrefix_ = digest(QByteArrayLiteral("[]"));
    } else if (next == "REGISTRY_OBSERVED") {
        const auto count = detail.value("events").toInt(-1);
        const auto prefix = checkedSha(detail.value("prefix_sha256"));
        require(id.isEmpty() && count >= registryEvents_ && (count != registryEvents_ || prefix == registryPrefix_),
                "A6_JOURNAL_REGISTRY_CHAIN_INVALID");
        registryEvents_ = count;
        registryPrefix_ = prefix;
    } else {
        require(id == identifier(id) && advances(decisions_.value(id), next), "A6_JOURNAL_INVALID_TRANSITION");
        decisions_.insert(id, next);
    }
    lastSeen_ = time;
    previousMac_ = mac;
    ++sequence_;
}

void A6Journal::append(const QString &state, const QString &id, const QJsonObject &detail, const QDateTime &now)
{
    require(healthy_, "A6_JOURNAL_DURABILITY_UNCERTAIN");
    require(now.isValid() && now >= lastSeen_, "CLOCK_ROLLBACK");
    verifyTrustedPath(trusted_);
    const QJsonObject event{{"schema", eventSchema}, {"sequence", sequence_}, {"previous_mac", QString::fromLatin1(previousMac_)},
        {"state", state}, {"decision_id", id}, {"at_utc", now.toUTC().toString(Qt::ISODateWithMs)}, {"detail", detail}};
    const auto payload = QJsonDocument(event).toJson(QJsonDocument::Compact);
    const auto mac = macFor(key_, payload);
    const QJsonObject envelope{{"event_b64", QString::fromLatin1(payload.toBase64())}, {"mac", QString::fromLatin1(mac)}};
    const auto line = QJsonDocument(envelope).toJson(QJsonDocument::Compact) + '\n';
    require(line.size() <= maximumEventSize, "A6_JOURNAL_INVALID_EVENT_SIZE");
    healthy_ = false;
    file_->append(line);
    apply(event, mac);
    healthy_ = true;
}

void A6Journal::observeRegistry(const QJsonArray &events, const QDateTime &now)
{
    require(now.isValid() && now >= lastSeen_, "CLOCK_ROLLBACK");
    require(events.size() >= registryEvents_, "REGISTRY_ROLLBACK");
    require(prefixDigest(events, registryEvents_) == registryPrefix_, "REGISTRY_HISTORY_CHANGED");
    append("REGISTRY_OBSERVED", {}, {{"events", static_cast<qint64>(events.size())},
        {"prefix_sha256", prefixDigest(events, events.size())}}, now);
}

void A6Journal::reserve(const QString &id, const QString &reviewSha, const QString &requestSha)
{
    identifier(id);
    require(state(id).isEmpty(), "DECISION_ALREADY_USED");
    const QJsonObject binding{{"review_sha256", checkedSha(reviewSha)}, {"request_sha256", checkedSha(requestSha)}};
    append("REQUESTED", id, binding, QDateTime::currentDateTimeUtc());
    append("AUTHORIZED_RESERVED", id, binding, QDateTime::currentDateTimeUtc());
}

void A6Journal::transition(const QString &id, const QString &next, const QJsonObject &detail)
{
    identifier(id);
    require(!state(id).isEmpty() && advances(state(id), next), "A6_JOURNAL_INVALID_TRANSITION");
    append(next, id, detail, QDateTime::currentDateTimeUtc());
}

QString A6Journal::state(const QString &id) const
{
    require(healthy_, "A6_JOURNAL_DURABILITY_UNCERTAIN");
    return decisions_.value(id);
}

} // namespace convergence
