onsole.error('Live translate frame error:', e);
    }
    await new Promise(r => setTimeout(r, 500)); // Sleep briefly between frames
  }
}
// --- END TRANSLATOR LOGIC ---

// --- CONVERSATION TTS LOGIC ---
let _ttsActive = false;
let _ttsQueue = [];
let _ttsIndex = 0;
let _characterProfiles = {};

function stopConversation() {
  _ttsActive = false;
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  const btn = document.getElementById('btn-play-conversation');
  if (btn) btn.innerHTML = '▶ Play Conversation';
}

function parseCharacterProfiles() {
  _characterProfiles = {};
  const container = document.getElementById('jlpt-lesson-tab-content');
  if (!container) return;
  
  const strongTags = container.querySelectorAll('strong');
  let charBlock = null;
  for (let i = 0; i <