document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("loader-overlay");
  const appShell = document.getElementById("app-shell");
  const lotusContainer = document.getElementById("loader-svg");
  lotusContainer.innerHTML = "";

  const svgNS = "http://www.w3.org/2000/svg";

  // === 🌌 ФОН ===
  document.body.style.background =
    "radial-gradient(circle at center, #1f1936 0%, #0a0815 100%)";

  // === ✨ CANVAS: частицы и дымка ===
  const canvas = document.createElement("canvas");
  Object.assign(canvas.style, {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    zIndex: "0",
    pointerEvents: "none",
  });
  document.body.insertBefore(canvas, document.body.firstChild);
  const ctx = canvas.getContext("2d");

  function resize() {
    canvas.width = innerWidth;
    canvas.height = innerHeight;
  }
  resize();
  window.addEventListener("resize", resize);

  const bgParticles = Array.from({ length: 160 }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    r: Math.random() * 1.6 + 0.3,
    alpha: Math.random() * 0.25 + 0.05,
    speedY: 0.1 + Math.random() * 0.2,
  }));

  function drawFog() {
    const g = ctx.createRadialGradient(
      canvas.width / 2,
      canvas.height / 2,
      0,
      canvas.width / 2,
      canvas.height / 2,
      canvas.width / 1.3
    );
    g.addColorStop(0, "rgba(90,80,200,0.12)");
    g.addColorStop(0.4, "rgba(50,40,120,0.08)");
    g.addColorStop(1, "rgba(10,10,30,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }

  function drawParticles() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    bgParticles.forEach((p) => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(170,160,255,${p.alpha})`;
      ctx.fill();
      p.y -= p.speedY;
      if (p.y < -5) {
        p.y = canvas.height + 5;
        p.x = Math.random() * canvas.width;
      }
    });
    drawFog();
    requestAnimationFrame(drawParticles);
  }
  drawParticles();

  // === 🌸 SVG ЛОТОС ===
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", "-160 -160 320 320");
  svg.setAttribute("width", "320");
  svg.setAttribute("height", "320");
  svg.style.position = "relative";
  svg.style.zIndex = "5";
  lotusContainer.appendChild(svg);

  const defs = document.createElementNS(svgNS, "defs");
  defs.innerHTML = `
    <radialGradient id="outerPetalGrad" r="80%">
      <stop offset="0%" stop-color="#f7f5ff"/>
      <stop offset="60%" stop-color="#c6bcff"/>
      <stop offset="100%" stop-color="#7f71f3"/>
    </radialGradient>
    <radialGradient id="innerPetalGrad" r="80%">
      <stop offset="0%" stop-color="#faf8ff"/>
      <stop offset="65%" stop-color="#bdb3ff"/>
      <stop offset="100%" stop-color="#6f61e6"/>
    </radialGradient>
    <filter id="petalShadow" x="-50%" y="-50%" width="200%" height="200%">
      <feDropShadow dx="0" dy="1.5" stdDeviation="3" flood-color="#5c50c7" flood-opacity="0.25"/>
    </filter>
  `;
  svg.appendChild(defs);

  const groupOutline = document.createElementNS(svgNS, "g");
  const groupOuter = document.createElementNS(svgNS, "g");
  const groupInner = document.createElementNS(svgNS, "g");
  svg.appendChild(groupOutline);
  svg.appendChild(groupOuter);
  svg.appendChild(groupInner);

  const outerPath = "M0,0 C30,-90,60,-90,0,-150 C-60,-90,-30,-90,0,0 Z";
  const innerPath = "M0,0 C20,-60,40,-60,0,-110 C-40,-60,-20,-60,0,0 Z";
  const outerAngles = [0, 25, -25, 50, -50];
  const innerAngles = [0, 15, -15, 35, -35];

  // === 1️⃣ Быстрая отрисовка линий ===
  function drawOutline() {
    const paths = [...outerAngles, ...innerAngles].map((angle, i) => {
      const p = document.createElementNS(svgNS, "path");
      const d = i < outerAngles.length ? outerPath : innerPath;
      p.setAttribute("d", d);
      p.setAttribute("transform", `rotate(${angle})`);
      p.setAttribute("fill", "none");
      p.setAttribute("stroke", "#b8b0ff");
      p.setAttribute("stroke-width", "1.3");
      p.style.opacity = "0.8";
      groupOutline.appendChild(p);
      return p;
    });

    paths.forEach((path, i) => {
      const len = path.getTotalLength();
      path.style.strokeDasharray = len;
      path.style.strokeDashoffset = len;
      setTimeout(() => {
        path.style.transition = "stroke-dashoffset 1s ease-out";
        path.style.strokeDashoffset = "0";
      }, i * 150);
    });

    return new Promise((resolve) => setTimeout(resolve, 2000));
  }

  // === 2️⃣ Мягкое раскрытие и дыхание ===
  function revealPetals() {
    groupOutline.style.transition = "opacity 0.8s ease";
    groupOutline.style.opacity = "0.3";

    function createPetal(group, pathData, fill, angle, delay) {
      const petal = document.createElementNS(svgNS, "path");
      petal.setAttribute("d", pathData);
      petal.setAttribute("fill", fill);
      petal.setAttribute("filter", "url(#petalShadow)");
      petal.style.opacity = "0";
      petal.style.transformOrigin = "0 0";
      petal.style.transform = `rotate(${angle}deg) scale(0.2)`;
      group.appendChild(petal);

      setTimeout(() => {
        petal.style.transition =
          "transform 1.2s cubic-bezier(.25,1,.3,1), opacity 1s ease";
        petal.style.opacity = "1";
        petal.style.transform = `rotate(${angle}deg) scale(1)`;

        // сразу начинаем дыхание
        const amp = 0.8 + Math.random() * 0.3;
        const scaleAmp = 0.01 + Math.random() * 0.005;
        (function breathe() {
          const t = Date.now() / (2600 + i * 200);
          const angleOffset = Math.sin(t) * amp;
          const scaleOffset = 1 + Math.sin(t * 1.3) * scaleAmp;
          petal.setAttribute(
            "transform",
            `rotate(${angle + angleOffset}) scale(${scaleOffset})`
          );
          requestAnimationFrame(breathe);
        })();
      }, delay);
    }

    outerAngles.forEach((a, i) =>
      createPetal(groupOuter, outerPath, "url(#outerPetalGrad)", a, i * 150)
    );
    innerAngles.forEach((a, i) =>
      createPetal(groupInner, innerPath, "url(#innerPetalGrad)", a, 600 + i * 150)
    );
  }

  // === 3️⃣ Растворение ===
  function dissolve() {
    const particles = [];
    for (let i = 0; i < 80; i++) {
      particles.push({
        x: canvas.width / 2 + (Math.random() - 0.5) * 60,
        y: canvas.height / 2 + (Math.random() - 0.5) * 40,
        vx: (Math.random() - 0.5) * 3,
        vy: (Math.random() - 0.5) * 2,
        size: Math.random() * 2 + 0.6,
        alpha: 1,
      });
    }

    function drawBurst() {
      particles.forEach((p, i) => {
        ctx.beginPath();
        ctx.rect(p.x, p.y, p.size, p.size);
        ctx.fillStyle = `rgba(190,180,255,${p.alpha})`;
        ctx.fill();
        p.x += p.vx;
        p.y += p.vy;
        p.alpha -= 0.018;
        if (p.alpha <= 0) particles.splice(i, 1);
      });
      requestAnimationFrame(drawBurst);
    }
    drawBurst();

    [...groupOuter.children, ...groupInner.children].forEach((petal) => {
      petal.style.transition = "opacity 1.8s ease, transform 2s ease";
      petal.style.opacity = "0";
      petal.style.transform += " scale(1.15)";
      petal.style.filter = "blur(3px) brightness(1.3)";
    });

    overlay.style.transition = "opacity 2s ease";
    overlay.style.opacity = 0;

    setTimeout(() => {
      overlay.remove();
      appShell.style.display = "flex";
      appShell.style.opacity = 0;
      appShell.style.transition = "opacity 1s ease";
      setTimeout(() => (appShell.style.opacity = 1), 100);
    }, 1500);
  }

  // === 🔁 Последовательность ===
  (async () => {
    await drawOutline();
    revealPetals();
    setTimeout(dissolve, 3000);
  })();
});
