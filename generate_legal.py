import re

with open('news.html', 'r', encoding='utf-8') as f:
    content = f.read()

head_match = re.search(r'([\s\S]*?)<div class="news-page-body"', content)
head_part = head_match.group(1) if head_match else ''

footer_match = re.search(r'(<!-- ══════════════════════════════════════════\s*FOOTER\s*══════════════════════════════════════════ -->[\s\S]*)', content)
footer_part = footer_match.group(1) if footer_match else ''

legal_body = '''
<div class="news-page-body" style="max-width: 900px; margin: 0 auto; padding: 40px 24px; min-height: 50vh;">
  <h1 style="font-family:'Playfair Display',serif;font-size:36px;color:var(--text);margin-bottom:16px;">Legal & Copyright Disclosure</h1>
  <p style="color:var(--text2); font-size:16px; margin-bottom:32px;">Comprehensive terms of service, disclosures, and policies for the VilfinTV platform.</p>

  <div style="font-size:16px;line-height:1.8;color:var(--text2); display: flex; flex-direction: column; gap: 32px;">
    
    <section>
      <h2 style="font-size:24px;color:var(--text);margin:0 0 12px;font-family:'Playfair Display',serif; border-bottom: 1px solid var(--border); padding-bottom: 8px;">1. Automated Market Assistant & Platform Overview</h2>
      <p style="margin-bottom:16px;">VilfinTV operates as an advanced automated market assistant and intelligent aggregation service across multiple verticals:</p>
      <ul style="margin-bottom:16px; padding-left: 24px;">
        <li style="margin-bottom:8px;"><strong>Financial Screener (Index):</strong> Real-time market data, algorithmic technical analysis, and screener tools are provided for informational tracking. Data is sourced from publicly available financial APIs and aggregated autonomously.</li>
        <li style="margin-bottom:8px;"><strong>News Aggregator:</strong> Headlines, summaries, and categorized stories are generated via intelligent search algorithms and automated processing of publicly available RSS feeds.</li>
        <li style="margin-bottom:8px;"><strong>Intelligence Hub & Web Stories:</strong> In-depth reports, blogs, and visual web stories are synthesized automatically using available market intelligence.</li>
        <li style="margin-bottom:8px;"><strong>Education Portal:</strong> Language learning resources (such as Japanese Kanji) and basic financial education materials are curated and presented for purely educational purposes.</li>
      </ul>
    </section>
    
    <section>
      <h2 style="font-size:24px;color:var(--text);margin:0 0 12px;font-family:'Playfair Display',serif; border-bottom: 1px solid var(--border); padding-bottom: 8px;">2. Informational & Educational Purposes Only</h2>
      <p style="margin-bottom:16px;">All content across the VilfinTV network—including stock screener metrics, news summaries, blog posts, and educational curricula—is provided strictly for informational and educational purposes. It does <strong>not</strong> constitute financial, investment, legal, tax, or professional advice.</p>
      <p style="margin-bottom:16px;">VilfinTV is not a registered broker, dealer, or investment advisor, and is not affiliated with any financial regulatory authority. Users should verify critical market data and news with primary sources or consult licensed financial advisors before making any investment decisions.</p>
    </section>

    <section>
      <h2 style="font-size:24px;color:var(--text);margin:0 0 12px;font-family:'Playfair Display',serif; border-bottom: 1px solid var(--border); padding-bottom: 8px;">3. Copyright & Intellectual Property</h2>
      <p style="margin-bottom:16px;">VilfinTV does not claim ownership of the original reporting, raw market data, or the underlying facts of the news events. Our intelligent algorithms synthesize available public data to provide structured, thematic summaries without reproducing source articles verbatim.</p>
      <p style="margin-bottom:16px;">Any trademarks, logos, brand names, and external media referenced on this platform are the property of their respective owners and are used solely for identification, commentary, or educational purposes under fair use doctrines.</p>
    </section>
    
    <section>
      <h2 style="font-size:24px;color:var(--text);margin:0 0 12px;font-family:'Playfair Display',serif; border-bottom: 1px solid var(--border); padding-bottom: 8px;">4. Third-Party Links & External Content</h2>
      <p style="margin-bottom:16px;">The VilfinTV platform may contain automated links to third-party websites or services that are not owned or controlled by us. We have no control over, and assume no responsibility for, the content, privacy policies, or practices of any third party websites. Accessing these external links is at your own risk.</p>
    </section>

    <section>
      <h2 style="font-size:24px;color:var(--text);margin:0 0 12px;font-family:'Playfair Display',serif; border-bottom: 1px solid var(--border); padding-bottom: 8px;">5. Disclaimer of Liability</h2>
      <p style="margin-bottom:16px;">While we strive to ensure the accuracy and timeliness of our automated screeners and news summaries, VilfinTV makes no warranties or representations regarding the completeness, accuracy, or reliability of the information. We shall not be held liable for any errors, omissions, or delays in this information or any financial losses, injuries, or damages arising from its display or use.</p>
    </section>
  </div>
</div>
'''

with open('legal.html', 'w', encoding='utf-8') as f:
    f.write(head_part + legal_body + footer_part)
