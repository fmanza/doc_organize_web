// Tema antes de que arranque React (2.3): aplica la copia local del tema del usuario para no pintar un instante con el
// tema equivocado. Fichero aparte porque la CSP no admite scripts en línea (`script-src 'self'`). La clave es
// COLOR_SCHEME_STORAGE_KEY de src/app/colorScheme.ts; «auto» (o nada guardado) sigue al sistema operativo.
(function () {
  try {
    var scheme = window.localStorage.getItem('mantine-color-scheme-value');
    if (scheme !== 'light' && scheme !== 'dark') {
      scheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-mantine-color-scheme', scheme);
  } catch (error) {
    // Sin localStorage (ventana privada, almacenamiento bloqueado): Mantine aplica el del sistema al arrancar.
  }
})();
