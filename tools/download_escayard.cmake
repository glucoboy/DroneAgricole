cmake_minimum_required(VERSION 3.20)

# Téléchargement reproductible du sous-ensemble EscaYard B7 utilisé pour la
# première baseline de cartographie. Les données restent exclues de Git.
get_filename_component(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(DESTINATION "${PROJECT_ROOT}/datasets/public/escayard/B7/raw")
file(MAKE_DIRECTORY "${DESTINATION}")

function(download_checked filename md5)
  set(url "https://zenodo.org/records/10362568/files/${filename}?download=1")
  set(output "${DESTINATION}/${filename}")
  message(STATUS "EscaYard: ${filename}")
  file(DOWNLOAD
    "${url}"
    "${output}"
    EXPECTED_HASH "MD5=${md5}"
    STATUS download_status
    SHOW_PROGRESS
    TLS_VERIFY ON
  )
  list(GET download_status 0 status_code)
  list(GET download_status 1 status_message)
  if(NOT status_code EQUAL 0)
    file(REMOVE "${output}")
    message(FATAL_ERROR "Téléchargement impossible (${status_code}): ${status_message}")
  endif()
endfunction()

download_checked(
  "trunk_locations_VineyardB7.zip"
  "ada3209607dd8e01a1e6bfa9fa6143c4"
)
download_checked(
  "datasheet.csv"
  "f3f33215b99e9c56411d4bd43e34e310"
)

set(TRUNK_ARCHIVE "${DESTINATION}/trunk_locations_VineyardB7.zip")
set(TRUNK_DIRECTORY "${DESTINATION}/trunk_locations_VineyardB7")
file(MAKE_DIRECTORY "${TRUNK_DIRECTORY}")
file(ARCHIVE_EXTRACT INPUT "${TRUNK_ARCHIVE}" DESTINATION "${TRUNK_DIRECTORY}")

if(DOWNLOAD_POINT_CLOUD)
  download_checked(
    "20220714_FLEXIGROBOTS_B7_30M0G_MS_PRO_Green_densified_point_cloud.las"
    "e9d08ac4c4c857a811faabcd51350bce"
  )
endif()

# Produit caméra optionnel de 3,4 Go. Il reste désactivé par défaut pour ne pas
# déclencher un téléchargement volumineux lors de l'installation géométrique.
if(DOWNLOAD_ORTHOMOSAIC)
  download_checked(
    "20220714_FLEXIGROBOTS_B7_30M0G_MS_PRO.tif"
    "13cec97cf9c19bbaa2436d290a3c3c1c"
  )
endif()

message(STATUS "Sous-ensemble EscaYard disponible dans ${DESTINATION}")
