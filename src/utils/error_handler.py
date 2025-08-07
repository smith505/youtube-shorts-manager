import sys

def handle_error(error_message):
    """Print error message to console"""
    print(f"ERROR: {error_message}", file=sys.stderr)

def main():
    try:
        # Example code that might raise an error
        result = 10 / 0
    except Exception as e:
        handle_error(str(e))
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)