chunking = "You are given an image which you are supposed to split into reasonably‑sized chunks. More specifically, split it into two (2) to five(5) chunks with ideally no more than 150 words each - when in doubt, rather add a chunk too much than one too few. Also make sure that, if possible, no chunk contains more than two ro three equations and content is more or less equally distributed between chunks. Your task is to output **only** the x and y coordinates of the top‑left and bottom‑right corner of each chunk, one chunk per line, in the following format: (x1, y1) (x2, y2) — where (x1, y1) is the top‑left corner and (x2, y2) is the bottom‑right corner of the rectangle. Coordinates must be integers in the pixel coordinate system of the original image, with (0, 0) at the top‑left of the image. Every written character must be covered by at least one chunk!! IMPORTANT: Lines of text at the border of chunks which would otherwise get split in a way that would encumber text recognition must be included in two chunks to ensure that proper OCR captures it at least once. Note that some lines of text are not quite straight - still make sure that the entire line of text is contained in at least one bounding box! *Never* distribute one mathematical expression over two chunks - the whole expression must be contained in one chunk! Do **not** output anything except the list of coordinate pairs. (The image is attached to this prompt as context.)"

