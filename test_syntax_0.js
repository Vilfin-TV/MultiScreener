
  // Silently rewrite legacy GitHub Pages path
  (function(){
    var p = window.location.pathname;
    if(p.indexOf('/MultiScreener') !== -1){
      history.replaceState(null,'','/');
    }
  })();
