import sys
from pathlib import Path

from streamlit.web import cli as stcli


APP_FILE = Path(__file__).with_name("check_polygon_delop.py")


def main():
    sys.argv = [
        "streamlit",
        "run",
        str(APP_FILE),
        "--global.developmentMode=false",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()
