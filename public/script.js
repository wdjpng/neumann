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

    fetch('/api/letters')
        .then(response => response.json())
        .then(async (letters) => {
            for (const letterId of letters) {
                // Fetch metadata from the letter's directory
                let letterMeta = {};
                try {
                    letterMeta = await fetch(`outputs_gpt-5_2/${letterId}/metadata.json`).then(r => r.json());
                } catch (error) {
                    console.error('Failed to fetch metadata for', letterId, error);
                }

                const item = document.createElement('div');
                item.className = 'letter-item';

                const title = document.createElement('h3');
                title.textContent = letterMeta?.title || letterId;

                const metaInfo = document.createElement('div');
                metaInfo.className = 'letter-meta';

                const person = document.createElement('span');
                person.className = 'letter-person';
                if (letterMeta) {
                    if (letterMeta.author && letterMeta.author !== 'John von Neumann') {
                        person.textContent = `From ${letterMeta.author}`;
                    } else if (letterMeta.recipient && letterMeta.recipient !== 'John von Neumann') {
                        person.textContent = `To ${letterMeta.recipient}`;
                    } else {
                        person.textContent = '';
                    }
                } else {
                    person.textContent = '';
                }

                const date = document.createElement('span');
                date.className = 'letter-person';
                if (letterMeta?.date && letterMeta.date !== 'unknown') {
                    date.textContent = letterMeta.date;
                }

                if (person.textContent) metaInfo.appendChild(person);
                if (date.textContent) metaInfo.appendChild(date);
                
                const linksDiv = document.createElement('div');
                linksDiv.className = 'letter-links';
                
                const pdfLink = document.createElement('a');
                pdfLink.href = `outputs_gpt-5_2/${letterId}/letter.pdf`;
                pdfLink.textContent = 'Original';
                linksDiv.appendChild(pdfLink);
                
                // Fetch and add English HTML link if available
                try {
                    const htmlFiles = await fetch(`/api/html-files/${letterId}`).then(r => r.json());
                    if (htmlFiles.html_en) {
                        const enLink = document.createElement('a');
                        enLink.href = `outputs_gpt-5_2/${letterId}/html_en.html`;
                        enLink.textContent = 'Translation';
                        linksDiv.appendChild(enLink);
                    }
                } catch (error) {
                    console.error('Failed to fetch HTML files for', letterId, error);
                }
                
                if (metaInfo.children.length > 0) item.appendChild(metaInfo);
                item.appendChild(title);
                item.appendChild(linksDiv);

                letterGallery.appendChild(item);
            }
        });
}); 
