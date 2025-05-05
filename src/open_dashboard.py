import webbrowser

def open_dashboard():
    """Open the ANPR dashboard in the default web browser."""
    url = "http://localhost:5000"  # Default Flask port
    try:
        webbrowser.open(url, new=2)  # new=2 opens in a new tab if possible
        print(f"Opened dashboard at {url}")
    except Exception as e:
        print(f"Error opening dashboard: {e}")

if __name__ == "__main__":
    open_dashboard()