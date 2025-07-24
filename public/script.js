document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('neumann-video');
    video.addEventListener('ended', function() {
        this.play();
    });

    const letterGallery = document.getElementById('letter-gallery');
    const debugToggle = document.getElementById('debug-toggle');
    let debugMode = false;
    let lettersData = [];

    // Debug mode toggle
    debugToggle.addEventListener('click', () => {
        debugMode = !debugMode;
        debugToggle.classList.toggle('active', debugMode);
        debugToggle.textContent = debugMode ? 'Exit Debug' : 'Debug Mode';
        
        // Toggle debug info visibility
        document.querySelectorAll('.debug-info').forEach(info => {
            info.classList.toggle('visible', debugMode);
        });
    });

    // Function to create debug info section
    async function createDebugInfo(letterId) {
        const debugInfo = document.createElement('div');
        debugInfo.className = 'debug-info';

        try {
            // Fetch HTML parts, HTML files, and chunks
            const [htmlParts, htmlFiles, chunks] = await Promise.all([
                fetch(`/api/html-parts/${letterId}`).then(r => r.json()),
                fetch(`/api/html-files/${letterId}`).then(r => r.json()),
                fetch(`/api/chunks/${letterId}`).then(r => r.json())
            ]);

            // HTML Parts section
            const partsSection = document.createElement('div');
            partsSection.className = 'debug-section';
            
            const partsTitle = document.createElement('h4');
            partsTitle.textContent = 'HTML Parts:';
            partsSection.appendChild(partsTitle);

            const partsLinks = document.createElement('div');
            partsLinks.className = 'debug-links';
            
            if (htmlParts.length > 0) {
                htmlParts.forEach(part => {
                    const link = document.createElement('a');
                    link.href = `html_parts/${part}`;
                    link.textContent = part.replace(`${letterId}_`, '').replace('.html', '');
                    link.target = '_blank';
                    partsLinks.appendChild(link);
                });
            } else {
                const noPartsMsg = document.createElement('span');
                noPartsMsg.textContent = 'No HTML parts found';
                noPartsMsg.style.fontStyle = 'italic';
                noPartsMsg.style.color = '#666';
                partsLinks.appendChild(noPartsMsg);
            }
            
            partsSection.appendChild(partsLinks);
            debugInfo.appendChild(partsSection);

            // Image Chunks section
            const chunksSection = document.createElement('div');
            chunksSection.className = 'debug-section';
            
            const chunksTitle = document.createElement('h4');
            chunksTitle.textContent = 'Image Chunks:';
            chunksSection.appendChild(chunksTitle);

            const chunksLinks = document.createElement('div');
            chunksLinks.className = 'debug-links';
            
            if (chunks.length > 0) {
                chunks.forEach(chunk => {
                    const link = document.createElement('a');
                    link.href = `chunks/${chunk}`;
                    link.textContent = chunk.replace(`${letterId}_`, '').replace('.jpg', '');
                    link.target = '_blank';
                    chunksLinks.appendChild(link);
                });
            } else {
                const noChunksMsg = document.createElement('span');
                noChunksMsg.textContent = 'No image chunks found';
                noChunksMsg.style.fontStyle = 'italic';  
                noChunksMsg.style.color = '#666';
                chunksLinks.appendChild(noChunksMsg);
            }
            
            chunksSection.appendChild(chunksLinks);
            debugInfo.appendChild(chunksSection);

            // Whole HTML files section
            const wholeSection = document.createElement('div');
            wholeSection.className = 'debug-section';
            
            const wholeTitle = document.createElement('h4');
            wholeTitle.textContent = 'Whole HTML Files:';
            wholeSection.appendChild(wholeTitle);

            const wholeLinks = document.createElement('div');
            wholeLinks.className = 'debug-links';

            if (htmlFiles.html_de) {
                const deLink = document.createElement('a');
                deLink.href = `html_de/${htmlFiles.html_de}`;
                deLink.textContent = 'German (DE)';
                deLink.target = '_blank';
                wholeLinks.appendChild(deLink);
            }

            if (htmlFiles.html_en) {
                const enLink = document.createElement('a');
                enLink.href = `html_en/${htmlFiles.html_en}`;
                enLink.textContent = 'English (EN)';
                enLink.target = '_blank';
                wholeLinks.appendChild(enLink);
            }

            if (!htmlFiles.html_de && !htmlFiles.html_en) {
                const noWholeMsg = document.createElement('span');
                noWholeMsg.textContent = 'No whole HTML files found';
                noWholeMsg.style.fontStyle = 'italic';
                noWholeMsg.style.color = '#666';
                wholeLinks.appendChild(noWholeMsg);
            }

            wholeSection.appendChild(wholeLinks);
            debugInfo.appendChild(wholeSection);

        } catch (error) {
            console.error('Failed to fetch debug info for', letterId, error);
            debugInfo.innerHTML = '<p style="color: red; font-style: italic;">Failed to load debug information</p>';
        }

        return debugInfo;
    }

    Promise.all([
        fetch('/api/letters').then(response => response.json()),
        fetch('/api/metadata').then(response => response.json())
    ]).then(async ([letters, metadata]) => {
        for (const letter of letters) {
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
            link.href = `samples/${letter}`;
            link.textContent = 'PDF';
            link.target = '_blank';
            
            item.appendChild(date);
            item.appendChild(person);
            item.appendChild(title);
            item.appendChild(link);

            // Add debug info
            const debugInfo = await createDebugInfo(letterId);
            item.appendChild(debugInfo);

            letterGallery.appendChild(item);
        }
    });
}); 