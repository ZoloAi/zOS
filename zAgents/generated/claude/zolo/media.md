zMedia: three events for things you show | declare WHAT + describe it, theme renders the right thing | real media in zBifrost, an openable block in zCLI

pick_one:
    zImage — a picture you own (any aspect ratio)
    zVideo — a clip you own (real player, native controls)
    zEmbed — a piece of the OUTSIDE web (YouTube/Vimeo/Spotify/Maps) from its ordinary link
    rule: own file, still? -> zImage | own file, moving? -> zVideo | someone else's page/player? -> zEmbed

shared: the shape every media event takes
    src      — what to show: a @.path file (zImage/zVideo) or a normal https link (zEmbed) — required
    alt_text — short description — REQUIRED, !optional; accessible by default + read by search
    caption  — optional line under it (credit, date, context)
    _zClass  — your class on the wrapper -> reskin (rounded, frame, glow, tilt); the declaration stays untouched
    short:   zImage: @.path  |  zEmbed: https://…   — one-line form when alt_text isn't needed
    spaces:  a path may contain spaces (My Reel.mov) — resolved + served fine (URL shows %20); tidy names just read cleaner

zImage: a still — real <img> in browser, openable block in zCLI
    keys:  src | alt_text | caption | _zClass
    aspect ratio: never reshaped — square / wide / tall / cinematic all shown as-is
    !sizing in the event — frame / shadow / tilt ride _zClass (your zBrush)

zVideo: a clip — real <video> player with native controls in browser
    keys:  src | alt_text | caption | _zClass   (same shared shape)
    poster:   a still shown before play (the cover image)
    loop:     true — restart when it ends
    muted:    true — silence the track (for a NON-autoplay player)
    autoplay: true — starts on load; browsers require muted, so zVideo MUTES it for you (don't also write muted)
    pattern:  ambient background clip = autoplay + loop (muted auto) | normal player = leave them off (+ poster)

zEmbed: the outside web — no iframe markup by hand
    src: the page's NORMAL link (youtube.com/watch?v=…) — zOS rewrites to the embeddable form per provider
    keys:  src | alt_text | caption | _zClass   (same shared shape)
    safe by default: only known providers (YouTube / Vimeo / Spotify / Maps) framed locked-down; unknown URL -> plain clickable link, never a silent iframe
    where: decided on the SERVER, not the browser — operator sets ZEMBED_MODE in zEnv: safe (allow-list, default) | trust (any https, internal app) | off
    !frameable (Stripe / PayPal / WooCommerce) -> !zEmbed; they ship a JS SDK widget -> Advanced/SDKWidgets

terminal: shared behaviour — a console can't paint media
    prints alt_text + path/address + caption, then asks: Open? (y/n) — opens in your system viewer / player / browser
    web app: y opens in YOUR new browser tab, never on the server — the media events read the room
    open_prompt: false — just print the details, no question (logs / reports)
    rule: nothing opens on its own — it always asks first
