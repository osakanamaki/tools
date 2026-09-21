"""開発環境の全体像をファイル出力する
-> Taskfile.yamlそのままでは日付取得(date, Get-Date)にOS間表記ゆれがあるため"""

import datetime
import subprocess

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"digest_{timestamp}.txt"

subprocess.run(
    ["gitingest", ".", "-e", "uv.lock,.python-version", "-o", filename],
    check=True,
)

print("-"*20)
print(f"Created {filename}")
print("-"*20)
