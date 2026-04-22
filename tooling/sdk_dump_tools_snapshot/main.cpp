#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include <sdkgenny.hpp>
#include <sdkgenny_parser.hpp>

static void strip_empty_includes(const std::filesystem::path& output_dir) {
    for (const auto& entry : std::filesystem::recursive_directory_iterator(output_dir)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".hpp") {
            continue;
        }

        std::ifstream input{entry.path()};
        if (!input) {
            continue;
        }

        std::vector<std::string> lines{};
        std::string line{};
        bool changed = false;

        while (std::getline(input, line)) {
            if (line == "#include \"\"") {
                changed = true;
                continue;
            }
            lines.emplace_back(line);
        }

        if (!changed) {
            continue;
        }

        std::ofstream output{entry.path(), std::ios::trunc};
        for (const auto& current_line : lines) {
            output << current_line << "\n";
        }
    }
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "usage: rq_sdkgenny_emit <input.genny> <output_dir>\n";
        return 1;
    }

    const auto input_path = std::filesystem::absolute(argv[1]);
    const auto output_dir = std::filesystem::absolute(argv[2]);

    if (!std::filesystem::exists(input_path)) {
        std::cerr << "input file not found: " << input_path << "\n";
        return 1;
    }

    sdkgenny::Sdk sdk{};
    sdkgenny::parser::State state{};
    state.filepath = input_path;
    state.parents.push_back(sdk.global_ns());

    try {
        tao::pegtl::file_input in{input_path.string()};
        if (!tao::pegtl::parse<sdkgenny::parser::Grammar, sdkgenny::parser::Action>(in, state)) {
            std::cerr << "parse failed: " << input_path << "\n";
            return 1;
        }
    } catch (const tao::pegtl::parse_error& e) {
        if (!e.positions().empty()) {
            const auto& p = e.positions().front();
            std::cerr << input_path << ":" << p.line << ":" << p.column << ": " << e.what() << "\n";
        } else {
            std::cerr << input_path << ": " << e.what() << "\n";
        }
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "unexpected parse error: " << e.what() << "\n";
        return 1;
    }

    std::filesystem::remove_all(output_dir);
    std::filesystem::create_directories(output_dir);
    sdk.generate(output_dir);
    strip_empty_includes(output_dir);

    std::cout << output_dir << "\n";
    return 0;
}
