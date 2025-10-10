document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('neumann-video');
    video.addEventListener('ended', function() {
        this.play();
    });

    const letterGallery = document.getElementById('letter-gallery');
    const qcLink = document.getElementById('qc-link');

    // Check debug mode and show QC link if enabled
    fetch('/api/debug-mode')
        .then(response => response.json())
        .then(data => {
            if (data.debug) {
                qcLink.style.display = 'inline-block';
            }
        })
        .catch(error => console.error('Failed to check debug mode:', error));

    Promise.all([
        fetch('/api/letters').then(response => response.json()),
        fetch('/api/metadata').then(response => response.json())
    ]).then(async ([letters, metadata]) => {
        for (const letterId of letters) {
            const letterMeta = metadata[letterId]?.metadata;

            const item = document.createElement('div');
            item.className = 'letter-item';

            const title = document.createElement('h3');
            title.textContent = letterMeta?.title || letterId;

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
            
            const linksDiv = document.createElement('div');
            linksDiv.className = 'letter-links';
            
            const pdfLink = document.createElement('a');
            pdfLink.href = `outputs_gpt-5_2/${letterId}/letter.pdf`;
            pdfLink.textContent = 'PDF';
            pdfLink.target = '_blank';
            linksDiv.appendChild(pdfLink);
            
            // Fetch and add German HTML link if available
            try {
                const htmlFiles = await fetch(`/api/html-files/${letterId}`).then(r => r.json());
                if (htmlFiles.html_de) {
                    const deLink = document.createElement('a');
                    deLink.href = `outputs_gpt-5_2/${letterId}/html_de.html`;
                    deLink.textContent = 'German';
                    deLink.target = '_blank';
                    linksDiv.appendChild(deLink);
                }
            } catch (error) {
                console.error('Failed to fetch HTML files for', letterId, error);
            }
            
            item.appendChild(person);
            item.appendChild(title);
            item.appendChild(linksDiv);

            letterGallery.appendChild(item);
        }
    });
}); 