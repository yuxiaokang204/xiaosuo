import py_compile, os, glob

base_dir = r"d:\trae\novel-agent-system-v1.1.0\src\backend"
errors = []
all_files = list(glob.glob(os.path.join(base_dir, "**", "*.py"), recursive=True))
for py_file in all_files:
    try:
        py_compile.compile(py_file, doraise=True)
    except Exception as e:
        errors.append((py_file, str(e)))

if errors:
    print("? 发现语法错误:")
    for f, e in errors:
        print(f"  {os.path.basename(f)}: {e}")
else:
    print(f"? 所有Python文件语法检查通过 ({len(all_files)}个文件)")
