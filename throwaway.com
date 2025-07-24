import os

dir = 'public/html'
for fname in os.listdir(dir):
    if fname.endswith('.jpg'):
        old_path = os.path.join(dir, fname)
        new_name = fname[:-4] + '.html'
        new_path = os.path.join(dir, new_name)
        with open(old_path, 'r') as f:
            lines = f.readlines()
        if len(lines) > 2:
            lines = lines[1:-1]
        with open(new_path, 'w') as f:
            f.writelines(lines)

