import os

png_files = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.lower().endswith('.png'):
            png_files.append(os.path.join(root, file))

png_files.sort()

for i, old_path in enumerate(png_files, start=1):
    file_name = os.path.basename(old_path)
    new_name = f'睿观({i}).png'
    new_path = os.path.join(os.path.dirname(old_path), new_name)
    os.rename(old_path, new_path)
    print(f'{old_path} -> {new_path}')
