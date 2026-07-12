export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        },
      });
    }

    const url = new URL(request.url);
    const action = url.searchParams.get('action');

    if (request.method === 'GET' && action === 'list') {
      // Require a secret token to read the list
      const auth = request.headers.get('Authorization');
      if (auth !== `Bearer ${env.ADMIN_SECRET}`) {
         return new Response('Unauthorized', { status: 401 });
      }
      
      const { results } = await env.DB.prepare('SELECT email FROM subscribers').all();
      const emails = results.map(r => r.email);
      return new Response(JSON.stringify(emails), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    if (request.method !== 'POST') {
      return new Response('Only POST method is allowed.', { status: 405 });
    }

    const email = url.searchParams.get('email');

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: 'Invalid email address' }), {
        status: 400,
        headers: { 'Access-Control-Allow-Origin': '*' }
      });
    }

    try {
      if (action === 'subscribe') {
        await env.DB.prepare('INSERT OR IGNORE INTO subscribers (email) VALUES (?)')
          .bind(email)
          .run();
      } else if (action === 'unsubscribe') {
        await env.DB.prepare('DELETE FROM subscribers WHERE email = ?')
          .bind(email)
          .run();
      } else {
        return new Response(JSON.stringify({ error: 'Invalid action' }), {
          status: 400,
          headers: { 'Access-Control-Allow-Origin': '*' }
        });
      }

      return new Response(JSON.stringify({ success: true, message: `Successfully ${action}d` }), {
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
