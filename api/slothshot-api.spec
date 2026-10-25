# PyInstaller recipe for the packaged api: one executable that unpacks itself on start.
# Built by scripts/build-api.mjs. Data files sit next to the `app` package, where the code looks
# for them, both in development and inside the binary:
#   prompts/  the versioned analysis prompt
#   data/     models.json, the tested model catalog the wizard reads
from PyInstaller.utils.hooks import collect_submodules

hidden = (
    collect_submodules("uvicorn")  # picked at run time by name (loops, protocols, lifespan)
    + collect_submodules("sqlalchemy.dialects.sqlite")
)
datas = [("prompts", "prompts"), ("data", "data")]

a = Analysis(
    ["entrypoint.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "mypy", "ruff"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="slothshot-api",
    console=True,
    upx=False,
)
