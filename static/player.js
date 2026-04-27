function initPlayer() {
  // No iframe needed, player is direct DOM
}

window.loadPlayerSong = function(src, title) {
  if (window.loadSong) {
    window.loadSong(src, title);
  }
};

window.playSong = function(src, title = 'Song') {
  loadPlayerSong(src, title);
};

// Interceptor for onclick=playSong buttons
document.addEventListener('click', function(e) {
  if (e.target.onclick && (e.target.onclick.toString().includes('playSong') || e.target.getAttribute('onclick')?.includes('playSong'))) {
    e.preventDefault();
    e.stopPropagation();
    const onclickStr = e.target.getAttribute('onclick') || e.target.onclick?.toString() || '';
    const srcMatch = onclickStr.match(/['\"\\/uploads\\/[^'\"]+\\.mp3['\"]/);
    if (srcMatch) {
      const src = srcMatch[0].replace(/['\"]/g, '');
      const songTitle = e.target.closest('div')?.querySelector('b, a, h1, h2, h3')?.textContent?.trim() || 'Song';
      loadPlayerSong(src, songTitle);
    }
  }
});

