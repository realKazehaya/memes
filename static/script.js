document.addEventListener('DOMContentLoaded', function() {
    // Función para cargar memes
    fetch('/api/memes')
        .then(response => response.json())
        .then(data => {
            const memesContainer = document.getElementById('memes');
            memesContainer.innerHTML = '';
            data.memes.forEach(meme => {
                const memeElement = document.createElement('div');
                memeElement.classList.add('meme');
                memeElement.innerHTML = `
                    <img src="${meme.meme_url}" alt="Meme">
                    <p>Likes: ${meme.likes}</p>
                `;
                memesContainer.appendChild(memeElement);
            });
        });
});