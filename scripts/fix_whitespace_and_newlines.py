import pathlib


def fix_file(p: pathlib.Path):
    text = p.read_text(encoding="utf-8")
    # Replace leading tabs with 4 spaces
    lines = text.splitlines()
    fixed = []
    changed = False
    for ln in lines:
        # replace leading tabs only
        new_ln = ln
        if new_ln.startswith("\t"):
            new_ln = new_ln.replace("\t", "    ")
            changed = True
        fixed.append(new_ln)
    # ensure newline at EOF
    out = "\n".join(fixed) + "\n"
    if out != text:
        p.write_text(out, encoding="utf-8")
        return True
    return changed


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    patterns = [
        "tradedesk/backend/routes/*.py",
        "tradedesk/backend/schemas/*.py",
        "tradedesk/backend/services/*.py",
    ]
    changed_files = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if fix_file(p):
                changed_files.append(str(p.relative_to(root)))
    if changed_files:
        print("Fixed files:")
        for f in changed_files:
            print(" -", f)
    else:
        print("No whitespace fixes needed")


if __name__ == "__main__":
    main()
