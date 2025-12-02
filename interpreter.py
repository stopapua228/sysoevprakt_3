import argparse
import pathlib
import struct
import xml.etree.ElementTree as ET


# Карта A -> (name, B_bits)
LAYOUT = {
    8:  ("CONST", 21),
    21: ("LOAD", 24),
    28: ("STORE", 0),
    25: ("MAX",   13),
}


def decode_word(word: int):
    """Разобрать 32-битное слово на A, имя команды и B."""
    A = word & 0x1F  # 5 бит
    if A not in LAYOUT:
        raise ValueError(f"Неизвестный opcode A={A}")
    name, B_bits = LAYOUT[A]
    if B_bits:
        B = (word >> 5) & ((1 << B_bits) - 1)
    else:
        B = None
    return A, name, B


class VM:
    def __init__(self):
        # Разреженная память: addr -> 32-битное значение
        self.mem: dict[int, int] = {}
        self.stack: list[int] = []
        self.pc: int = 0        # program counter (в ячейках, не в байтах)
        self.prog_len: int = 0  # количество команд

    # ----- Работа с памятью -----

    def mem_get(self, addr: int) -> int:
        if addr < 0:
            raise IndexError("Отрицательный адрес памяти")
        return self.mem.get(addr, 0)

    def mem_set(self, addr: int, value: int) -> None:
        if addr < 0:
            raise IndexError("Отрицательный адрес памяти")
        self.mem[addr] = value & 0xFFFFFFFF

    # ----- Загрузка программы -----

    def load_program(self, path: str) -> None:
        """Читает бинарник, кладёт каждое 32-бит слово в mem[0..n-1]."""
        blob = pathlib.Path(path).read_bytes()
        if len(blob) % 4 != 0:
            raise ValueError("Размер бинарного файла не кратен 4 байтам")
        words = [
            int.from_bytes(blob[i : i + 4], "little")
            for i in range(0, len(blob), 4)
        ]
        for i, w in enumerate(words):
            self.mem_set(i, w)
        self.prog_len = len(words)
        self.pc = 0

    # ----- Интерпретация -----

    def step(self) -> bool:
        """Выполнить одну команду. Возвращает False, если программа закончилась."""
        if self.pc >= self.prog_len:
            return False

        word = self.mem_get(self.pc)
        self.pc += 1

        A, name, B = decode_word(word)

        if name == "CONST":
            # push B
            self.stack.append(B)

        elif name == "LOAD":
            # push mem[B]
            val = self.mem_get(B)
            self.stack.append(val)

        elif name == "STORE":
            # stack: [..., VALUE, ADDR]
            if len(self.stack) < 2:
                raise RuntimeError("STORE: недостаточно элементов в стеке")
            addr = self.stack.pop()
            val = self.stack.pop()
            self.mem_set(addr, val)

        elif name == "MAX":
            # stack: [..., X, BASE]
            if len(self.stack) < 2:
                raise RuntimeError("MAX: недостаточно элементов в стеке")
            base_addr = self.stack.pop()
            x = self.stack.pop()
            y = self.mem_get(base_addr + B)
            self.stack.append(max(x, y))

        else:
            raise RuntimeError(f"Неизвестная команда: {name}")

        return True

    def run(self, max_steps: int = 1_000_000) -> None:
        """Запускает программу до конца или до превышения лимита шагов."""
        steps = 0
        while self.pc < self.prog_len:
            if steps >= max_steps:
                raise RuntimeError("Превышен лимит шагов интерпретатора")
            self.step()
            steps += 1

    # ----- Дамп памяти в XML -----

    def dump_xml(self, out_path: str, start: int, end: int) -> None:
        """
        Создаёт XML-дамп памяти с адресами [start, end).
        """
        root = ET.Element("memory")
        root.set("start", str(start))
        root.set("end", str(end))

        for addr in range(start, end):
            cell = ET.SubElement(root, "cell")
            cell.set("addr", str(addr))
            cell.set("value", str(self.mem_get(addr)))

        tree = ET.ElementTree(root)
        tree.write(out_path, encoding="utf-8", xml_declaration=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Interpreter for UVM Variant 30")
    parser.add_argument("program", help="Путь к бинарному файлу программы (.bin)")
    parser.add_argument("dump", help="Путь к XML-файлу дампа памяти")
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Начальный адрес дампа (включительно)",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=64,
        help="Конечный адрес дампа (не включительно)",
    )
    args = parser.parse_args(argv)

    vm = VM()
    vm.load_program(args.program)
    vm.run()
    vm.dump_xml(args.dump, args.start, args.end)

    print(f"Программа выполнена. Дамп памяти сохранён в: {args.dump}")


if __name__ == "__main__":
    main()
