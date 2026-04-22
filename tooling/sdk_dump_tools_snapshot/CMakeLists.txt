cmake_minimum_required(VERSION 3.24)

project(rq_sdkgenny_emit LANGUAGES CXX)

set(SDKGENNY_BUILD_PARSER ON CACHE BOOL "" FORCE)
add_subdirectory("E:/Github/sdkgenny" sdkgenny-build)

add_executable(rq_sdkgenny_emit
    main.cpp
)

target_link_libraries(rq_sdkgenny_emit PRIVATE sdkgenny::sdkgenny)

target_compile_features(rq_sdkgenny_emit PRIVATE cxx_std_23)

if(TARGET taocpp::pegtl)
    target_link_libraries(rq_sdkgenny_emit PRIVATE taocpp::pegtl)
endif()

if(DEFINED pegtl_SOURCE_DIR)
    target_include_directories(rq_sdkgenny_emit PRIVATE "${pegtl_SOURCE_DIR}/include")
endif()
