cmake_minimum_required(VERSION 3.20)

# Sous-ensemble brut minimal de FriûlBot Test 2 — 22-07-2024. Les bags NDVI,
# GNDVI et NDRE dérivés par les auteurs ne sont volontairement pas téléchargés.
get_filename_component(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(SEQUENCE_ROOT "${PROJECT_ROOT}/datasets/public/friulbot/test2/2024-07-22")
set(BAG_DIRECTORY "${SEQUENCE_ROOT}/raw")
set(IMAGE_DIRECTORY "${SEQUENCE_ROOT}/multispectral")
file(MAKE_DIRECTORY "${BAG_DIRECTORY}" "${IMAGE_DIRECTORY}")

function(download_checked filename destination md5)
  set(output "${destination}/${filename}")
  if(EXISTS "${output}")
    file(MD5 "${output}" current_md5)
    if(current_md5 STREQUAL md5)
      message(STATUS "FriulBot: ${filename} déjà présent et vérifié")
      return()
    endif()
  endif()
  set(url "https://zenodo.org/api/records/13983719/files/${filename}/content")
  message(STATUS "FriulBot: téléchargement de ${filename}")
  file(DOWNLOAD "${url}" "${output}"
    EXPECTED_HASH "MD5=${md5}"
    STATUS download_status
    SHOW_PROGRESS
    TLS_VERIFY ON)
  list(GET download_status 0 status_code)
  list(GET download_status 1 status_message)
  if(NOT status_code EQUAL 0)
    file(REMOVE "${output}")
    message(FATAL_ERROR "Téléchargement impossible (${status_code}): ${status_message}")
  endif()
endfunction()

download_checked("2024-07-22-11-03-15.bag" "${BAG_DIRECTORY}" "f79aac2893a0b910863962fbd9a9a2bf")
download_checked("0029SET.zip" "${IMAGE_DIRECTORY}" "14ded790d1771006218fc02980ee3eb8")

set(IMAGE_ARCHIVE "${IMAGE_DIRECTORY}/0029SET.zip")
set(EXTRACTED_IMAGES "${IMAGE_DIRECTORY}/0029SET")
if(NOT EXISTS "${EXTRACTED_IMAGES}")
  # L'archive contient déjà le répertoire racine 0029SET.
  file(ARCHIVE_EXTRACT INPUT "${IMAGE_ARCHIVE}" DESTINATION "${IMAGE_DIRECTORY}")
endif()

message(STATUS "FriûlBot Test 2 disponible dans ${SEQUENCE_ROOT}")
