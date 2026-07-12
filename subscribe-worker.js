/**
 * Cloudflare Worker to securely manage the subscribers.json file in GitHub.
 * It requires a GitHub PAT stored as a Cloudflare Secret: GITHUB_PAT
 */

const REPO = 'Vilfin-TV/MultiScreener';
const FILE_PATH = 'subscribers.json';

export default {
  async fetch(request, env) {
    // Handle CORS preflight requests
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      });
    }

    if (request.method !== 'POST') {
      return new Response('Only POST method is allowed.', { status: 405 });
    }

    const url = new URL(request.url);
    const action = url.searchParams.get('action');
    const email = url.searchParams.get('email');

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: 'Invalid email address' }), {
        status: 400,
        headers: { 'Access-Control-Allow-Origin': '*' }
      });
    }

    const githubToken = env.GITHUB_PAT;
    if (!githubToken) {
      return new Response(JSON.stringify({ error: 'GitHub PAT is not configured in worker secrets' }), {
        status: 500,
        headers: { 'Access-Control-Allow-Origin': '*' }
      });
    }

    const apiUrl = `https://api.github.com/repos/${REPO}/contents/${FILE_PATH}`;

    try {
      // 1. Get the current file contents and SHA
      const getResp = await fetch(apiUrl, {
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'User-Agent': 'Cloudflare-Worker',
          'Accept': 'application/vnd.github.v3+json'
        }
      });

      if (!getResp.ok) {
        throw new Error(`Failed to fetch file: ${await getResp.text()}`);
      }

      const getJson = await getResp.json();
      const sha = getJson.sha;
      
      // Decode base64 content
      let contentStr = atob(getJson.content.replace(/\n/g, ''));
      let subscribers = [];
      try {
        subscribers = JSON.parse(contentStr);
      } catch (e) {
        subscribers = [];
      }

      // 2. Modify the list
      let updated = false;
      if (action === 'subscribe') {
        if (!subscribers.includes(email)) {
          subscribers.push(email);
          updated = true;
        }
      } else if (action === 'unsubscribe') {
        const initialLength = subscribers.length;
        subscribers = subscribers.filter(e => e !== email);
        if (subscribers.length !== initialLength) {
          updated = true;
        }
      } else {
        return new Response(JSON.stringify({ error: 'Invalid action' }), {
          status: 400,
          headers: { 'Access-Control-Allow-Origin': '*' }
        });
      }

      if (!updated) {
        return new Response(JSON.stringify({ success: true, message: 'No changes needed' }), {
          status: 200,
          headers: { 'Access-Control-Allow-Origin': '*' }
        });
      }

      // 3. Commit the new file
      const newContentBase64 = btoa(JSON.stringify(subscribers, null, 2));
      const putResp = await fetch(apiUrl, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${githubToken}`,
          'User-Agent': 'Cloudflare-Worker',
          'Accept': 'application/vnd.github.v3+json'
        },
        body: JSON.stringify({
          message: `${action === 'subscribe' ? 'Add' : 'Remove'} subscriber via automated worker`,
          content: newContentBase64,
          sha: sha
        })
      });

      if (!putResp.ok) {
        throw new Error(`Failed to update file: ${await putResp.text()}`);
      }

      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Access-Control-Allow-Origin': '*' }
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), {
        status: 500,
        headers: { 'Access-Control-Allow-Origin': '*' }
      });
    }
  }
};
