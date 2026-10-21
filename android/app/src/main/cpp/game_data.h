#pragma once
#include <cstdio>
#include <dirent.h>
#include <sys/stat.h>
#include <string>
#include <stdexcept>
#include <android/log.h>

constexpr const char* kGameRoot = "/storage/emulated/0/nfsc";
inline void checkGameData() {
    const std::string root(kGameRoot);
    FILE* exe = std::fopen((root + "/NFSC.exe").c_str(), "rb");
    if (!exe) throw std::runtime_error("Cannot read Internal storage/nfsc/NFSC.exe; check files and storage permission");
    unsigned char magic[2]{};
    const size_t read = std::fread(magic, 1, 2, exe);
    std::fclose(exe);
    struct stat info{};
    if (read != 2 || magic[0] != 'M' || magic[1] != 'Z' ||
        stat((root + "/NFSC.exe").c_str(), &info) || info.st_size != 7217152)  // NFSC.exe 1.4, SHA-256 baaaaec3...2fd3
        throw std::runtime_error("NFSC.exe does not match the expected Carbon 1.4 image size/header");
    // Carbon's data folders (the shared storage is case-insensitive).
    for (const char* name : {"CARS", "FRONTEND", "GLOBAL", "LANGUAGES", "MOVIES", "NIS", "SOUND", "TRACKS"}) {
        const auto path = root + "/" + name;
        DIR* dir = opendir(path.c_str());
        if (!dir) throw std::runtime_error("Cannot read game directory: " + path);
        unsigned files = 0;
        while (auto* entry = readdir(dir)) if (entry->d_name[0] != '.') ++files;
        closedir(dir);
        if (!files) throw std::runtime_error("Empty game directory: " + path);
        __android_log_print(ANDROID_LOG_INFO, "NFSC", "Data directory %s: %u entries", name, files);
    }
    __android_log_print(ANDROID_LOG_INFO, "NFSC", "Game data readable at %s; executable header/size OK (guest not running)", kGameRoot);
}
