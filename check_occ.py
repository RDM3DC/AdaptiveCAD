try:
    import OCC
    print('OCC module is available')
except ImportError as e:
    print(f'Error: {e}')
