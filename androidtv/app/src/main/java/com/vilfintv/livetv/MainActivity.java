package com.vilfintv.livetv;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
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

    // Map the Nvidia Shield remote to the web player. D-pad arrows + OK are left
    // to the WebView (they reach the page as key events and drive the spatial
    // focus navigation); here we wire the media transport + BACK.
    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        switch (keyCode) {
            case KeyEvent.KEYCODE_BACK:
                // Exit a full-screen video first, then walk in-app history
                // (player → providers via pushState), then let the OS quit.
                if (customView != null) {
                    web.getWebChromeClient().onHideCustomView();
                    return true;
                }
                if (web.canGoBack()) {
                    web.goBack();
                    return true;
                }
                break;

            case KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE:
            case KeyEvent.KEYCODE_MEDIA_PLAY:
            case KeyEvent.KEYCODE_MEDIA_PAUSE:
                js("window.__tvControl&&window.__tvControl.playPause()");
                return true;

            case KeyEvent.KEYCODE_MEDIA_FAST_FORWARD:
            case KeyEvent.KEYCODE_MEDIA_NEXT:
            case KeyEvent.KEYCODE_CHANNEL_UP:
                js("window.__tvControl&&window.__tvControl.next()");
                return true;

            case KeyEvent.KEYCODE_MEDIA_REWIND:
            case KeyEvent.KEYCODE_MEDIA_PREVIOUS:
            case KeyEvent.KEYCODE_CHANNEL_DOWN:
                js("window.__tvControl&&window.__tvControl.prev()");
                return true;

            case KeyEvent.KEYCODE_MENU:
                js("window.__tvControl&&window.__tvControl.filters()");
                return true;
        }
        return super.onKeyDown(keyCode, event);
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
