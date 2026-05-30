const fs = require('fs');
let html = fs.readFileSync('education.html', 'utf8');

const oldStr = `  } else {
    document.getElementById('toggle-jlpt').classList.add('active');
    document.getElementById('cbse-container').style.display = 'none';
    document.getElementById('jlpt-container').style.display = 'block';
    renderJlptContent();
  }`;

const newStr = `  } else {
    document.getElementById('toggle-jlpt').classList.add('active');
    document.getElementById('cbse-container').style.display = 'none';
    document.getElementById('jlpt-container').style.display = 'block';
    switchJlptLevel(_activeJlptLevel);
  }`;

html = html.replace(oldStr, newStr);

const oldStrCrLf = oldStr.replace(/\n/g, '\r\n');
if (html.indexOf(oldStrCrLf) !== -1) {
    html = html.replace(oldStrCrLf, newStr.replace(/\n/g, '\r\n'));
}

fs.writeFileSync('education.html', html);
console.log('Successfully updated switchHub');
