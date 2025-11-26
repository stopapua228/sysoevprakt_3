import argparse
import pathlib
import struct
import sys

try:
    import yaml
except ImportError:
    yaml = None

# Описание опкодов и ширины поля B
OPCODES = {
    "CONST": {"A": 8,  "B_bits": 21, "arg": "value"},
    "LOAD":  {"A": 21, "B_bits": 24, "arg": "addr"},
    "STORE": {"A": 28, "B_bits": 0,  "arg": None},
    "MAX":   {"A": 25, "B_bits": 13, "arg": "offset"},
}


def assemble_instruction(ins: dict) -> dict:

    if "op" not in ins:
        raise ValueError(f"Инструкция без поля 'op': {ins}")
    op = ins["op"].upper()
    if op not in OPCODES:
        raise ValueError(f"Неизвестная команда: {op}")

    meta = OPCODES[op]
    A = meta["A"] & 0x1F          # 5 бит
    B_bits = meta["B_bits"]
    arg_name = meta["arg"]

    if B_bits == 0:
        B = None
    else:
        if arg_name not in ins:
            raise ValueError(f"{op} требует аргумент '{arg_name}'")
        B = int(ins[arg_name])
        maxB = (1 << B_bits) - 1
        if not (0 <= B <= maxB):
            raise ValueError(
                f"{op}: значение поля B={B} не в диапазоне 0..{maxB}"
            )

    # Упаковка: word = A | (B << 5)
    value = A
    if B is not None:
        value |= (B << 5)
    value &= 0xFFFFFFFF

    return {"op": op, "A": A, "B": B, "word": value}


def assemble_program(src_path: str, out_path: str, test_mode: bool = False) -> None:
    """Собрать программу из YAML в бинарник .bin"""
    if yaml is None:
        raise RuntimeError(
            "Для работы ассемблера нужен PyYAML. "
            "Установите: pip install pyyaml"
        )

    src = pathlib.Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"Исходный файл не найден: {src_path}")

    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Файл программы YAML должен быть списком инструкций")

    ir = [assemble_instruction(ins) for ins in data]

    # Запись бинарника
    out_file = pathlib.Path(out_path)
    with out_file.open("wb") as f:
        for item in ir:
            f.write(struct.pack("<I", item["word"]))

    size = out_file.stat().st_size

    # Всегда печатаем размер в байтах (требование этапа 2)
    print(f"Ассемблировано команд: {len(ir)}")
    print(f"Размер бинарного файла: {size} байт")

    if test_mode:
        # Внутреннее представление, как требуют на этапе 1
        print("\nВнутреннее представление (IR):")
        for i, item in enumerate(ir):
            if item["B"] is None:
                print(f"{i:02d}: op={item['op']}, A={item['A']}")
            else:
                print(f"{i:02d}: op={item['op']}, A={item['A']}, B={item['B']}")

        # И байты в hex, как в тестах спецификации
        blob = out_file.read_bytes()
        print("\nБайты (hex):")
        print(" ".join(f"0x{b:02X}," for b in blob).rstrip(","))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assembler for UVM Variant 30")
    parser.add_argument("source", help="Путь к YAML-файлу с программой")
    parser.add_argument("out", help="Путь к выходному бинарному файлу (.bin)")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Режим тестирования: печать IR и байтов",
    )
    args = parser.parse_args(argv)

    assemble_program(args.source, args.out, args.test)


if __name__ == "__main__":
    main()
