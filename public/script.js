document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('neumann-video');
    video.addEventListener('ended', function() {
        this.play();
    });

    const letterGallery = document.getElementById('letter-gallery');

    Promise.all([
        fetch('/api/letters').then(response => response.json()),
        fetch('/api/metadata').then(response => response.json())
    ]).then(([letters, metadata]) => {
        letters.forEach(letter => {
            const letterId = letter.replace('.pdf', '');
            const letterMeta = metadata[letterId]?.metadata;

            const item = document.createElement('div');
            item.className = 'letter-item';

            const title = document.createElement('h3');
            title.textContent = letterMeta?.title || letterId;

            const date = document.createElement('span');
            date.className = 'letter-date';
            date.textContent = letterMeta?.date || 'Unknown Date';

            const person = document.createElement('span');
            person.className = 'letter-person';
            if (letterMeta) {
                if (letterMeta.author && letterMeta.author !== 'John von Neumann') {
                    person.textContent = `By ${letterMeta.author}`;
                } else if (letterMeta.recipient && letterMeta.recipient !== 'John von Neumann') {
                    person.textContent = `To ${letterMeta.recipient}`;
                } else {
                    person.textContent = '';
                }
            } else {
                person.textContent = '';
            }
            
            const link = document.createElement('a');
            link.href = `samples2/${letter}`;
            link.textContent = 'PDF';
            link.target = '_blank';
            
            item.appendChild(date);
            item.appendChild(person);
            item.appendChild(title);
            item.appendChild(link);

            letterGallery.appendChild(item);
        });
    });
}); 