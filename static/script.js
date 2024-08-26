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
                    <button class="like-button" data-id="${meme.id}">Like</button>
                `;
                memesContainer.appendChild(memeElement);
            });

            // Añadir eventos de clic a los botones de like
            document.querySelectorAll('.like-button').forEach(button => {
                button.addEventListener('click', function() {
                    const memeId = this.getAttribute('data-id');
                    fetch(`/like/${memeId}`, { method: 'POST' })
                        .then(response => response.json())
                        .then(data => {
                            if (data.error) {
                                alert(data.error);
                            } else {
                                this.previousElementSibling.textContent = `Likes: ${data.likes}`;
                            }
                        });
                });
            });
        });
});
