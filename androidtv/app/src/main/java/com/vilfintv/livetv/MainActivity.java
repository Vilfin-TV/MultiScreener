package com.vilfintv.livetv;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.content.Context;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.ValueCallback;
import android.widget.FrameLayout;

/**
 * VilfinTV Live TV — Android TV / Nvidia Shield wrapper.
 *
 * Loads the live web app (IPTV + Jio TV only, via ?app=tv) inside a
 * hardware-accelerated WebView tuned for D-pad navigation and full-screen
 * HLS playback. No local content is bundled — everything streams from the
 * existing VilfinTV backend, so the app never needs rebuilding for channel
 * or guide changes.
 */
public class MainActivity extends Activity {

    // The web app entry point. ?app=tv restricts the hub to IPTV + Jio TV and
    // enables the remote-focus styling shipped in iptv.html.
    private static final String APP_URL = "https://vilfintv.com/iptv.html?app=tv";

    private WebView web;

    // True once the page's window.__tvNav bridge is confirmed present. Until then
    // we do NOT swallow remote keys — we let the WebView handle them natively, so
    // the D-pad still works even if the bridge is slow/absent (older WebView, load
    // hiccup, etc.). Re-checked on every page load.
    private volatile boolean webNavReady = false;

    // Full-screen video plumbing (WebChromeClient custom view for <video> fullscreen).
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private FrameLayout fullscreenContainer;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Immersive full-bleed surface; keep the screen awake while watching.
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        fullscreenContainer = new FrameLayout(this);
        fullscreenContainer.setBackgroundColor(0xFF000000);

        web = new WebView(this);
        web.setBackgroundColor(0xFF04091A);
        // Critical for Android TV login: the WebView must be focusable in touch
        // mode so focusing an <input> from the D-pad triggers the on-screen
        // (Leanback) keyboard for username/password entry.
        web.setFocusable(true);
        web.setFocusableInTouchMode(true);

        // Debug builds only: expose the WebView to Chrome DevTools so the CI
        // emulator test can inspect page state and script login. The flashed
        // release APK is not debuggable, so this is a no-op there — no remote
        // debugging surface ships to real devices.
        if ((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);                 // localStorage: login token, favourites
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // HLS autoplay
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setJavaScriptCanOpenWindowsAutomatically(true);
        s.setSupportMultipleWindows(false);
        // A desktop-ish UA so the site serves its full 10-foot layout.
        s.setUserAgentString(s.getUserAgentString() + " VilfinTV-AndroidTV/1.0");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                String url = req.getUrl().toString();
                // Keep VilfinTV navigation inside the app; ignore any stray
                // external links (the TV build exposes none, but be safe).
                if (url.contains("vilfintv.com") || url.contains("workers.dev")) {
                    view.loadUrl(url);
                }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                webNavReady = false;   // bridge not defined yet on the new page
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                // Confirm the page's remote bridge is live before we start
                // intercepting keys. Retry briefly in case scripts run late.
                confirmBridge(0);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onShowCustomView(View view, CustomViewCallback callback) {
                if (customView != null) { callback.onCustomViewHidden(); return; }
                customView = view;
                customViewCallback = callback;
                fullscreenContainer.addView(customView, new FrameLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
                web.setVisibility(View.GONE);
                fullscreenContainer.setVisibility(View.VISIBLE);
                fullscreenContainer.bringToFront();
            }

            @Override
            public void onHideCustomView() {
                if (customView == null) return;
                fullscreenContainer.removeView(customView);
                customView = null;
                fullscreenContainer.setVisibility(View.GONE);
                web.setVisibility(View.VISIBLE);
                if (customViewCallback != null) customViewCallback.onCustomViewHidden();
            }
        });

        FrameLayout root = new FrameLayout(this);
        root.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        root.addView(fullscreenContainer, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        fullscreenContainer.setVisibility(View.GONE);
        setContentView(root);

        if (savedInstanceState != null) {
            web.restoreState(savedInstanceState);
        } else {
            web.loadUrl(APP_URL);
        }

        // Ensure the WebView holds focus so the very first D-pad press lands on
        // the login username field rather than being swallowed by the window.
        web.requestFocus();
    }

    /** Run a JS snippet on the WebView (UI thread). */
    private void js(final String code) {
        if (web == null) return;
        web.post(new Runnable() {
            @Override public void run() { web.evaluateJavascript(code, null); }
        });
    }

    /** Poll the page for window.__tvNav; flip webNavReady on once it exists. */
    private void confirmBridge(final int attempt) {
        if (web == null) return;
        web.evaluateJavascript("(typeof window.__tvNav==='function')", new ValueCallback<String>() {
            @Override public void onReceiveValue(String v) {
                boolean ok = "true".equals(v);
                webNavReady = ok;
                if (!ok && attempt < 12 && web != null) {
                    web.postDelayed(new Runnable() {
                        @Override public void run() { confirmBridge(attempt + 1); }
                    }, 400);
                }
            }
        });
    }

    // Keys whose behaviour lives in the web bridge (window.__tvNav / __tvControl).
    // BACK is intentionally excluded — it must always work (exit fullscreen/app).
    private boolean isBridgeKey(int kc) {
        return isNavKey(kc)
            || kc == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE || kc == KeyEvent.KEYCODE_MEDIA_PLAY
            || kc == KeyEvent.KEYCODE_MEDIA_PAUSE || kc == KeyEvent.KEYCODE_MEDIA_FAST_FORWARD
            || kc == KeyEvent.KEYCODE_MEDIA_NEXT || kc == KeyEvent.KEYCODE_CHANNEL_UP
            || kc == KeyEvent.KEYCODE_MEDIA_REWIND || kc == KeyEvent.KEYCODE_MEDIA_PREVIOUS
            || kc == KeyEvent.KEYCODE_CHANNEL_DOWN || kc == KeyEvent.KEYCODE_MENU;
    }

    private void showKeyboard() {
        InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null && web != null) {
            web.requestFocus();
            imm.showSoftInput(web, InputMethodManager.SHOW_IMPLICIT);
        }
    }

    // CAPTURE THE REMOTE BEFORE THE WEBVIEW. Android WebView does not reliably
    // route D-pad arrows to the page's focus system (they get swallowed by the
    // <video> element or lost on the player screen), which is why on-screen
    // navigation felt dead. We intercept every press here and drive the web
    // app's __tvNav() explicitly, so focus movement is deterministic. When the
    // leanback keyboard is open it owns the keys (its own window), so typing is
    // unaffected.
    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        int kc = event.getKeyCode();
        // FAIL-SAFE: until the web bridge is confirmed loaded, do NOT swallow
        // remote keys — let the WebView route them natively. Otherwise a missing
        // bridge (older WebView, slow load) would leave the whole D-pad dead.
        if (!webNavReady && isBridgeKey(kc)) {
            return super.dispatchKeyEvent(event);
        }
        if (event.getAction() != KeyEvent.ACTION_DOWN) {
            // Consume the matching UP for keys we handle so they don't leak.
            if (isNavKey(kc)) return true;
            return super.dispatchKeyEvent(event);
        }
        switch (kc) {
            case KeyEvent.KEYCODE_DPAD_UP:    js("window.__tvNav&&window.__tvNav('up')");    return true;
            case KeyEvent.KEYCODE_DPAD_DOWN:  js("window.__tvNav&&window.__tvNav('down')");  return true;
            case KeyEvent.KEYCODE_DPAD_LEFT:  js("window.__tvNav&&window.__tvNav('left')");  return true;
            case KeyEvent.KEYCODE_DPAD_RIGHT: js("window.__tvNav&&window.__tvNav('right')"); return true;

            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_NUMPAD_ENTER:
                if (web != null) {
                    web.post(new Runnable() {
                        @Override public void run() {
                            web.evaluateJavascript("window.__tvNav?window.__tvNav('ok'):''", new ValueCallback<String>() {
                                @Override public void onReceiveValue(String v) {
                                    // v is a JSON string, e.g. "\"input\"" for a text field.
                                    if (v != null && v.contains("input")) showKeyboard();
                                }
                            });
                        }
                    });
                }
                return true;

            case KeyEvent.KEYCODE_BACK:
                // Native <video> fullscreen (WebChromeClient custom view) exits first.
                if (customView != null) { web.getWebChromeClient().onHideCustomView(); return true; }
                // Otherwise let the web app handle BACK in order: exit page/CSS
                // fullscreen → player → provider hub. __tvControl.back() returns
                // truthy when it consumed the press; only then do we stop. If it
                // didn't (e.g. already on the provider hub), fall back to history
                // or let the OS close the app.
                if (web != null) {
                    web.post(new Runnable() {
                        @Override public void run() {
                            web.evaluateJavascript(
                                "(window.__tvControl&&window.__tvControl.back())?'1':'0'",
                                new ValueCallback<String>() {
                                    @Override public void onReceiveValue(String v) {
                                        if (v == null || !v.contains("1")) {
                                            if (web.canGoBack()) web.goBack();
                                            else finish();
                                        }
                                    }
                                });
                        }
                    });
                    return true;
                }
                return super.dispatchKeyEvent(event);   // let the OS exit

            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                js("window.__tvControl&&window.__tvControl.playPause()"); return true;
            case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
            case KeyEvent.KEYCODE_MEDIA_NEXT:
            case KeyEvent.KEYCODE_CHANNEL_UP:
                js("window.__tvControl&&window.__tvControl.next()"); return true;
            case KeyEvent.KEYCODE_MEDIA_REWIND:
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
            case KeyEvent.KEYCODE_CHANNEL_DOWN:
                js("window.__tvControl&&window.__tvControl.prev()"); return true;
            case KeyEvent.KEYCODE_MENU:
                js("window.__tvControl&&window.__tvControl.filters()"); return true;
        }
        return super.dispatchKeyEvent(event);
    }

    private boolean isNavKey(int kc) {
        return kc == KeyEvent.KEYCODE_DPAD_UP || kc == KeyEvent.KEYCODE_DPAD_DOWN
            || kc == KeyEvent.KEYCODE_DPAD_LEFT || kc == KeyEvent.KEYCODE_DPAD_RIGHT
            || kc == KeyEvent.KEYCODE_DPAD_CENTER || kc == KeyEvent.KEYCODE_ENTER
            || kc == KeyEvent.KEYCODE_NUMPAD_ENTER;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onPause() {
        super.onPause();
        web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.loadUrl("about:blank");
            web.destroy();
        }
        super.onDestroy();
    }
}
