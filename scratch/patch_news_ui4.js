const fs = require('fs');

let content = fs.readFileSync('news.html', 'utf8');

const newRenderFn = `let breakingNewsData = null;
let bnActiveContinent = 'Asia';
let bnActiveRegion = 'India National';

window.bnSetContinent = function(continent) {
  bnActiveContinent = continent;
  bnActiveRegion = Object.keys(breakingNewsData[continent])[0];
  bnRefreshUI();
};
window.bnSetRegion = function(region) {
  bnActiveRegion = region;
  bnRefreshUI();
};
window.bnRefreshUI = function() {
  var oldWrapper = document.getElementById('breaking-news-wrapper');
  if (oldWrapper) {
    var newWrapper = renderBreakingNews(breakingNewsData);
    oldWrapper.parentNode.replaceChild(newWrapper, oldWrapper);
  }
};

function renderBreakingNews(data) {
  if (!data || Object.keys(data).length === 0) return document.createElement('div');
  breakingNewsData = data;
  
  if (!data[bnActiveContinent]) {
    bnActiveContinent = Object.keys(data)[0];
  }
  if (bnActiveContinent && !data[bnActiveContinent][bnActiveRegion]) {
    bnActiveRegion = Object.keys(data[bnActiveContinent])[0];
  }

  var wrapper = document.createElement('div');
  wrapper.className = 'news-section';
  wrapper.style.marginBottom = '20px';
  wrapper.id = 'breaking-news-wrapper';

  var html = '<div class="news-section-header">' +
             '<div style="display:flex;align-items:center;gap:12px">' +
             '<div class="news-section-name" style="color: #ef4444;">🚨 Breaking News</div>' +
             '</div>' +
             '<button class="news-section-toggle" onclick="toggleNewsSection(this)" aria-expanded="true" aria-label="Toggle section"><svg viewBox="0 0 24 24"><path d="M12 8l-6 6 1.41 1.41L12 10.83l4.59 4.58L18 14l-6-6z"/></svg></button>' +
             '</div>';

  html += '<div class="news-section-content" id="breaking-news-content">';
  
  // Primary Tabs
  html += '<div class="ml-cat-tabs" style="border-radius: 6px 6px 0 0;">';
  Object.keys(data).forEach(function(continent) {
    var activeCls = (continent === bnActiveContinent) ? ' active' : '';
    html += '<div class="ml-cat-tab' + activeCls + '" onclick="bnSetContinent(\\'' + esc(continent) + '\\')">' + esc(continent) + '</div>';
  });
  html += '</div>';

  // Secondary Tabs
  if (bnActiveContinent && data[bnActiveContinent]) {
    html += '<div class="ml-cat-tabs" style="background:var(--card); border-bottom:1px solid var(--border); padding-left:10px;">';
    Object.keys(data[bnActiveContinent]).forEach(function(region) {
      var activeCls = (region === bnActiveRegion) ? ' active' : '';
      html += '<div class="ml-cat-tab' + activeCls + '" style="font-size:10.5px; padding:6px 10px;" onclick="bnSetRegion(\\'' + esc(region) + '\\')">' + esc(region) + '</div>';
    });
    html += '</div>';
  }

  var items = (bnActiveContinent && bnActiveRegion && data[bnActiveContinent][bnActiveRegion]) ? data[bnActiveContinent][bnActiveRegion] : [];
  
  html += '<div class="breaking-news-grid" style="padding-top:16px; border-top:1px solid var(--border);">';
  if (items.length > 0) {
    var heroItem = items[0];
    var sideItems = items.slice(1, 5);

    function _ca(item) {
        var encSnippet = item.description ? encodeURIComponent(item.description) : '';
        return 'role="button" tabindex="0" data-title="' + escAttr(item.title) + '" data-snippet="' + encSnippet + '" data-url="' + escAttr(item.link) + '" data-source="' + escAttr(item.source || '') + '" onclick="lnbCardOpen(this)"';
    }

    html += '<div class="bn-hero" ' + _ca(heroItem) + '>' +
            '<img src="' + escAttr(heroItem.imageUrl) + '" alt="">' +
            '<div class="bn-hero-content">' +
            '<div class="bn-badge">BREAKING</div>' +
            '<div class="bn-hero-title">' + esc(heroItem.title) + '</div>' +
            (heroItem.description ? '<div class="bn-hero-desc">' + esc(heroItem.description) + '</div>' : '') +
            '</div></div>';

    if (sideItems.length > 0) {
      html += '<div class="bn-side-grid">';
      sideItems.forEach(function(item) {
        var timeStr = 'Just now';
        if (item.publishedAt) {
          var ms = Date.now() - item.publishedAt;
          var mins = Math.floor(ms/60000);
          if (mins < 60) timeStr = mins + 'm ago';
          else timeStr = Math.floor(mins/60) + 'h ago';
        }
        html += '<div class="bn-card" ' + _ca(item) + '>' +
                (item.imageUrl ? '<img src="' + escAttr(item.imageUrl) + '" alt="">' : '') +
                '<div class="bn-card-content">' +
                '<div class="bn-card-title">' + esc(item.title) + '</div>' +
                '<div class="bn-card-meta">' + timeStr + ' &middot; ' + esc(item.source || '') + '</div>' +
                '</div></div>';
      });
      html += '</div>';
    }
  } else {
    html += '<div style="padding:20px; color:var(--text3);">No breaking news found for this region.</div>';
  }
  
  html += '</div></div>';

  wrapper.innerHTML = html;
  return wrapper;
}`;

content = content.replace(/function renderBreakingNews\(items\) \{[\s\S]*?return wrapper;\r?\n\}/, newRenderFn);

fs.writeFileSync('news.html', content);
console.log('Successfully patched news.html!');
