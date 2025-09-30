<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Purdue Men's Basketball — Team Hub Pro</title>
  <meta name="description" content="One-stop Purdue Men's Basketball hub: breaking news, insider analysis, videos, rankings, and schedule — updated automatically.">
  <link rel="stylesheet" href="static/css/pro.css" />
</head>
<body>
  <!-- Header -->
  <header class="header" role="banner">
    <div class="wrap bar">
      <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Open menu" aria-controls="mobileDrawer" aria-expanded="false">☰</button>
      <div class="brand">
        <img id="logo" alt="Team Logo" />
        <h1 id="wordmark">Team Hub</h1>
      </div>
      <nav class="nav" aria-label="Primary"></nav>
      <div class="controls">
        <button class="btn ghost" id="refreshBtn" type="button">Refresh</button>
      </div>
    </div>

    <!-- Always-visible slim subnav (scrollable chips) -->
    <div class="subnav-wrap">
      <div class="wrap">
        <nav id="subNav" class="subnav" aria-label="Quick links"></nav>
      </div>
    </div>

    <div class="ticker" aria-live="polite">
      <div class="ticker-track" id="tickerTrack"></div>
    </div>
  </header>

  <!-- Mobile drawer -->
  <aside id="mobileDrawer" class="drawer" aria-hidden="true">
    <div class="drawer-panel" role="dialog" aria-label="Menu">
      <div class="drawer-head">
        <div class="drawer-title">Menu</div>
        <button class="drawer-close" id="drawerClose" aria-label="Close menu">✕</button>
      </div>
      <nav id="mobileNav" class="drawer-nav" aria-label="Mobile"></nav>
      <div class="drawer-actions">
        <button class="btn ghost block" id="drawerRefresh">Refresh</button>
      </div>
    </div>
    <div class="drawer-backdrop" id="drawerBackdrop"></div>
  </aside>

  <!-- Hero -->
  <section class="hero">
    <div class="wrap hero-inner">
      <a id="featureLink" class="feature-hero" target="_blank" rel="noopener">
        <img id="featureImg" alt="Featured image" />
        <div class="feature-overlay">
          <div class="feature-chip">
            <span id="featureTrust"></span> <span id="featureSource"></span>
          </div>
          <h1 id="featureTitle">Top Story</h1>
          <p id="featureSummary"></p>
          <time id="featureWhen"></time>
        </div>
      </a>
    </div>
  </section>

  <!-- Main grid -->
  <main class="wrap main-grid">
    <section class="panel">
      <div class="head">
        <h2>Videos & Highlights</h2>
        <div class="carousel-ctrls">
          <button class="ctrl" id="prevVid" aria-label="Previous videos">←</button>
          <button class="ctrl" id="nextVid" aria-label="Next videos">→</button>
        </div>
      </div>
      <div class="body"><div class="carousel" id="videoCarousel"></div></div>
    </section>

    <section class="panel">
      <div class="head"><h2>Latest Headlines</h2></div>
      <div class="body"><div class="news-grid" id="newsGrid"></div></div>
    </section>

    <section class="panel">
      <div class="head"><h2>Insider Coverage</h2></div>
      <div class="body"><div class="news-grid" id="insiderGrid"></div></div>
    </section>

    <aside class="sidebar">
      <section class="panel widget">
        <div class="head"><h3>Upcoming Schedule</h3></div>
        <div class="body"><div class="schedule-list" id="scheduleList"></div></div>
      </section>

      <section class="panel widget">
        <div class="head"><h3>Rankings</h3></div>
        <div class="body" id="rankingsBox">
          <div class="rank-row"><strong>AP Poll:</strong> <span id="apRank">—</span></div>
          <div class="rank-row"><strong>KenPom:</strong> <span id="kpRank">—</span></div>
        </div>
      </section>

      <section class="panel widget">
        <div class="head"><h3>NIL Leaderboard</h3></div>
        <div class="body"><ol class="nil-list" id="nilList"></ol></div>
      </section>
    </aside>
  </main>

  <footer class="footer"><div class="wrap">© Team Hub Pro — Purdue Men's Basketball</div></footer>
  <script src="static/js/pro.js"></script>
</body>
</html>