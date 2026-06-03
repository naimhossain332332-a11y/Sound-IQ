// ── Canvas Particle System ──
const canvas = document.getElementById("bg-canvas");
const ctx = canvas.getContext("2d");

let W, H;
function resize() {
  W = canvas.width = window.innerWidth;
  H = canvas.height = window.innerHeight;
}
resize();
window.addEventListener("resize", resize);

const mouse = { x: -9999, y: -9999, active: false };

document.addEventListener("mousemove", (e) => {
  mouse.x = e.clientX;
  mouse.y = e.clientY;
  mouse.active = true;
});

document.addEventListener("mouseleave", () => { mouse.active = false; });

document.addEventListener("touchmove", (e) => {
  const t = e.touches[0];
  mouse.x = t.clientX;
  mouse.y = t.clientY;
  mouse.active = true;
}, { passive: true });

document.addEventListener("touchend", () => { mouse.active = false; }, { passive: true });

const colors = [
  [0, 255, 204], [123, 97, 255], [255, 107, 157], [255, 193, 7], [0, 204, 153], [100, 200, 255]
];

class Particle {
  constructor() {
    this.x = Math.random() * W;
    this.y = Math.random() * H;
    this.vx = (Math.random() - 0.5) * 0.3;
    this.vy = (Math.random() - 0.5) * 0.3;
    const c = colors[Math.floor(Math.random() * colors.length)];
    this.r = c[0]; this.g = c[1]; this.b = c[2];
    this.alpha = 0.06 + Math.random() * 0.18;
    this.size = 1.5 + Math.random() * 3;
    this.baseSize = this.size;
    this.angle = Math.random() * Math.PI * 2;
  }

  update() {
    this.angle += (Math.random() - 0.5) * 0.025;
    this.vx += Math.cos(this.angle) * 0.002;
    this.vy += Math.sin(this.angle) * 0.002;

    if (mouse.active) {
      const mx = mouse.x - this.x;
      const my = mouse.y - this.y;
      const dist = Math.sqrt(mx * mx + my * my);
      if (dist < 200) {
        const force = (200 - dist) / 200;
        const a = Math.atan2(my, mx);
        this.vx -= Math.cos(a) * force * 1.2;
        this.vy -= Math.sin(a) * force * 1.2;
        this.size = this.baseSize + force * 6;
        this.r = Math.min(255, this.r + force * 30);
        this.g = Math.min(255, this.g + force * 20);
        this.b = Math.min(255, this.b + force * 30);
      } else {
        this.size += (this.baseSize - this.size) * 0.04;
      }
    }

    this.vx *= 0.97;
    this.vy *= 0.97;
    this.x += this.vx;
    this.y += this.vy;

    if (this.x < -30) this.x = W + 30;
    if (this.x > W + 30) this.x = -30;
    if (this.y < -30) this.y = H + 30;
    if (this.y > H + 30) this.y = -30;
  }

  draw() {
    ctx.globalAlpha = this.alpha;
    ctx.fillStyle = `rgb(${this.r | 0},${this.g | 0},${this.b | 0})`;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
    ctx.fill();
  }
}

const count = Math.min(180, Math.max(80, (W * H) / 8000));
const particles = Array.from({ length: count | 0 }, () => new Particle());

function drawWeb() {
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const dx = particles[i].x - particles[j].x;
      const dy = particles[i].y - particles[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const maxDist = mouse.active ? 160 : 120;
      if (dist < maxDist) {
        const a = (1 - dist / maxDist) * 0.06;
        ctx.globalAlpha = a;
        const r = (particles[i].r + particles[j].r) / 2 | 0;
        const g = (particles[i].g + particles[j].g) / 2 | 0;
        const b = (particles[i].b + particles[j].b) / 2 | 0;
        ctx.strokeStyle = `rgb(${r},${g},${b})`;
        ctx.lineWidth = 0.6;
        ctx.beginPath();
        ctx.moveTo(particles[i].x, particles[i].y);
        ctx.lineTo(particles[j].x, particles[j].y);
        ctx.stroke();
      }
    }
  }
}

function drawVignette() {
  const g = ctx.createRadialGradient(W * 0.5, H * 0.5, 0, W * 0.5, H * 0.5, W * 0.55);
  g.addColorStop(0, "rgba(0,255,204,.015)");
  g.addColorStop(0.35, "rgba(123,97,255,.008)");
  g.addColorStop(1, "transparent");
  ctx.globalAlpha = 1;
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, W, H);
}

function animateParticles() {
  ctx.clearRect(0, 0, W, H);
  for (const p of particles) { p.update(); p.draw(); }
  drawWeb();
  drawVignette();
  requestAnimationFrame(animateParticles);
}
animateParticles();

// ── Liquid Glass Blobs — Spring Physics ──
const blobs = [
  document.getElementById("blob1"),
  document.getElementById("blob2"),
  document.getElementById("blob3"),
  document.getElementById("blob4"),
];

const blobPhysics = blobs.map((_, i) => ({
  x: window.innerWidth * (0.2 + i * 0.2),
  y: window.innerHeight * (0.2 + (i % 2) * 0.4),
  vx: 0,
  vy: 0,
  stiffness: 0.003 + (i * 0.001),
  damping: 0.88 - (i * 0.01),
  homeX: window.innerWidth * (0.2 + i * 0.2),
  homeY: window.innerHeight * (0.2 + (i % 2) * 0.4),
}));

function updateBlobs() {
  for (let i = 0; i < blobs.length; i++) {
    const b = blobPhysics[i];
    let tx = b.homeX;
    let ty = b.homeY;

    if (mouse.active) {
      const mx = mouse.x - b.x;
      const my = mouse.y - b.y;
      const dist = Math.sqrt(mx * mx + my * my);
      if (dist < 500) {
        const strength = (500 - dist) / 500;
        tx += (mouse.x - b.homeX) * strength * 0.15;
        ty += (mouse.y - b.homeY) * strength * 0.15;
      }
    }

    const dx = tx - b.x;
    const dy = ty - b.y;
    b.vx += dx * b.stiffness;
    b.vy += dy * b.stiffness;
    b.vx *= b.damping;
    b.vy *= b.damping;
    b.x += b.vx;
    b.y += b.vy;

    blobs[i].style.transform = `translate(${b.x - blobs[i].offsetWidth / 2}px, ${b.y - blobs[i].offsetHeight / 2}px)`;
  }
  requestAnimationFrame(updateBlobs);
}

window.addEventListener("resize", () => {
  for (let i = 0; i < blobPhysics.length; i++) {
    blobPhysics[i].homeX = window.innerWidth * (0.2 + i * 0.2);
    blobPhysics[i].homeY = window.innerHeight * (0.2 + (i % 2) * 0.4);
  }
});

updateBlobs();

// ── Cursor Glow ──
const glow = document.getElementById("cursorGlow");

document.addEventListener("mousemove", (e) => {
  glow.style.transform = `translate(${e.clientX}px, ${e.clientY}px) translate(-50%, -50%)`;
});

document.addEventListener("mouseenter", () => { glow.style.opacity = "1"; });
document.addEventListener("mouseleave", () => { glow.style.opacity = "0"; });

// ── Navbar ──
const navbar = document.querySelector(".navbar");
const navBar = document.querySelector(".nav-bar");

window.addEventListener("scroll", () => {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  navBar.style.width = ((window.scrollY / max) * 100) + "%";
  const o = Math.min(0.6 + window.scrollY / 500, 0.92);
  navbar.style.background = `rgba(8,9,12,${o})`;
});

// ── Hamburger ──
const toggle = document.getElementById("navToggle");
const links = document.getElementById("navLinks");

toggle.addEventListener("click", () => {
  toggle.classList.toggle("active");
  links.classList.toggle("open");
});

document.querySelectorAll(".nav-link").forEach((l) => {
  l.addEventListener("click", () => {
    toggle.classList.remove("active");
    links.classList.remove("open");
  });
});

// ── Card Reveal ──
const cards = document.querySelectorAll(".card");

const cardObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        const delay = parseInt(e.target.getAttribute("data-reveal")) || 0;
        setTimeout(() => e.target.classList.add("reveal"), delay);
        cardObserver.unobserve(e.target);
      }
    });
  },
  { threshold: 0.08 }
);

cards.forEach((c) => cardObserver.observe(c));

// ── Button Ripple ──
document.querySelectorAll(".btn").forEach((btn) => {
  btn.addEventListener("click", function (e) {
    const r = this.getBoundingClientRect();
    const size = Math.max(r.width, r.height);
    const x = e.clientX - r.left - size / 2;
    const y = e.clientY - r.top - size / 2;
    const ripple = document.createElement("span");
    ripple.style.cssText = `
      position:absolute;width:${size}px;height:${size}px;left:${x}px;top:${y}px;
      border-radius:50%;background:rgba(255,255,255,.12);pointer-events:none;
      transform:scale(0);animation:rippleAnim .55s ease-out forwards
    `;
    this.appendChild(ripple);
    setTimeout(() => ripple.remove(), 550);
  });
});

const ripples = document.createElement("style");
ripples.textContent = `@keyframes rippleAnim{to{transform:scale(2.5);opacity:0}}`;
document.head.appendChild(ripples);

// ── Dynamic Glass Blur Depth ──
const glassCards = document.querySelectorAll(".glass-card");
window.addEventListener("scroll", () => {
  glassCards.forEach((gc) => {
    const rect = gc.getBoundingClientRect();
    const viewH = window.innerHeight;
    const center = rect.top + rect.height / 2;
    const dist = Math.abs(center - viewH / 2) / (viewH / 2);
    const blur = 12 + dist * 8;
    gc.style.backdropFilter = `blur(${blur}px)`;
    gc.style.webkitBackdropFilter = `blur(${blur}px)`;
  });
});
