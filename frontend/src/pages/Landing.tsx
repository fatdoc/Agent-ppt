import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Copy,
  FileOutput,
  FileText,
  ImageIcon,
  Layers,
  Menu,
  RefreshCw,
  Type,
  Wand2,
  X,
} from 'lucide-react';

const accent = '#AFFF00';

const navLinks = [
  { label: '首页', href: '#hero' },
  { label: 'Harness', href: '#formula' },
  { label: '场景', href: '#scenarios' },
  { label: '参考', href: '#references' },
  { label: '入口', href: '#entry' },
];

const scenarios = [
  {
    name: '创新创业比赛',
    tagline: '让证据进入链路',
    description: '从材料接入、论证编排到视觉校验，把核心竞争力放进可追踪的交付链。',
    image: '/images/scene-pitch.png',
    color: '#84cc16',
    tint: 'from-lime-400/20 via-lime-400/10 to-transparent',
    badges: ['材料接入', '论证链路', '评审焦点', '交付记录'],
  },
  {
    name: '工作汇报',
    tagline: '让过程可复盘',
    description: '把复杂进展整理成阶段、证据与结论，让每一页都能回到来源和判断。',
    image: '/images/scene-report.png',
    color: '#f59e0b',
    tint: 'from-amber-400/20 via-amber-400/10 to-transparent',
    badges: ['阶段状态', '结论先行', '证据留痕', '风格一致'],
  },
  {
    name: '融资路演',
    tagline: '让判断有校验',
    description: '用 Harness 式检查点组织叙事、指标和风险，把信念变成经得住追问的页面。',
    image: '/images/scene-roadshow.png',
    color: accent,
    tint: 'from-[#AFFF00]/20 via-[#AFFF00]/5 to-transparent',
    badges: ['叙事编排', '指标校验', '风险补位', '强焦点'],
  },
];

const formula = [
  {
    icon: Layers,
    title: '接入',
    subtitle: 'Ingest',
    description: '统一收束材料、数据、截图和旧稿',
    color: accent,
  },
  {
    icon: Type,
    title: '编排',
    subtitle: 'Plan',
    description: '把意图、论点和证据排成可执行链路',
    color: '#FF6B35',
  },
  {
    icon: ImageIcon,
    title: '校验',
    subtitle: 'Verify',
    description: '先看结构与风格，再批量生成页面',
    color: '#00D4FF',
  },
  {
    icon: FileOutput,
    title: '交付',
    subtitle: 'Ship',
    description: '输出可展示、可编辑、可追踪的 PPT',
    color: accent,
  },
];

const entries = [
  {
    icon: Wand2,
    title: '快速 Harness',
    description: '从一个主题开始，让 Agent 自动搭建结构、节奏与页面初稿。',
    cta: '启动链路',
  },
  {
    icon: FileText,
    title: '材料接入',
    description: '把材料、数据与文字交给系统，转化为可编排的页面资产。',
    cta: '接入材料',
  },
  {
    icon: Copy,
    title: '参考复用',
    description: '上传参考作品，抽取它的结构、语气与视觉约束。',
    cta: '接入参考',
  },
  {
    icon: RefreshCw,
    title: '旧稿重构',
    description: '让旧稿进入工程流水线，重新获得秩序、风格和交付质量。',
    cta: '重构旧稿',
  },
];

const references = [
  { image: '/images/ref-1.png', label: '封面' },
  { image: '/images/ref-2.png', label: '数据' },
  { image: '/images/ref-3.png', label: '图文' },
  { image: '/images/ref-4.png', label: '目录' },
  { image: '/images/ref-5.png', label: '对比' },
  { image: '/images/ref-6.png', label: '收束' },
];

const footerLinks = [
  { title: '入口', links: ['快速 Harness', '材料接入', '参考复用', '旧稿重构'] },
  { title: '场景', links: ['创新创业比赛', '工作汇报', '教学课件', '融资路演'] },
  { title: '文化', links: ['Harness 工程', '校验优先', '来源留痕', '稳定交付'] },
  { title: '条款', links: ['隐私政策', '服务条款', '数据安全'] },
];

const scrollToId = (href: string) => {
  document.querySelector(href)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const useScrolled = () => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 48);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return scrolled;
};

const ClickSpark: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sparksRef = useRef<Array<{ x: number; y: number; angle: number; startedAt: number }>>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    if (!canvas || !parent) return;

    const resize = () => {
      const rect = parent.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = rect.width * ratio;
      canvas.height = rect.height * ratio;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(parent);

    let frame = 0;
    const draw = (timestamp: number) => {
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const ratio = window.devicePixelRatio || 1;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      sparksRef.current = sparksRef.current.filter((spark) => {
        const progress = (timestamp - spark.startedAt) / 420;
        if (progress >= 1) return false;

        const eased = progress * (2 - progress);
        const distance = eased * 22;
        const length = 12 * (1 - eased);
        const x1 = spark.x + distance * Math.cos(spark.angle);
        const y1 = spark.y + distance * Math.sin(spark.angle);
        const x2 = spark.x + (distance + length) * Math.cos(spark.angle);
        const y2 = spark.y + (distance + length) * Math.sin(spark.angle);

        ctx.strokeStyle = accent;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
        return true;
      });

      frame = requestAnimationFrame(draw);
    };

    frame = requestAnimationFrame(draw);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);

  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const startedAt = performance.now();

    sparksRef.current.push(
      ...Array.from({ length: 8 }, (_, index) => ({
        x,
        y,
        angle: (Math.PI * 2 * index) / 8,
        startedAt,
      })),
    );
  };

  return (
    <div className="relative min-h-screen overflow-hidden" onClick={handleClick}>
      <canvas ref={canvasRef} className="pointer-events-none fixed inset-0 z-[100]" />
      {children}
    </div>
  );
};

export const Landing: React.FC = () => {
  const navigate = useNavigate();
  const scrolled = useScrolled();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [email, setEmail] = useState('');
  const currentScenario = scenarios[scenarioIndex];

  const goCreate = () => navigate('/app');
  const nextScenario = () => setScenarioIndex((value) => (value + 1) % scenarios.length);
  const previousScenario = () => setScenarioIndex((value) => (value + scenarios.length - 1) % scenarios.length);

  return (
    <ClickSpark>
      <main className="landing-page min-h-screen bg-white text-[#121212]">
        <nav
          className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
            scrolled ? 'border-b border-white/10 bg-[#121212]/95 backdrop-blur-md' : 'bg-transparent'
          }`}
        >
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 md:px-6">
            <button
              type="button"
              onClick={() => scrollToId('#hero')}
              className="landing-rise flex items-baseline gap-1.5 text-left text-2xl font-black tracking-normal"
            >
              <span className="text-[#AFFF00]">兰台</span>
              <span className={`font-mono text-sm ${scrolled ? 'text-white/70' : 'text-[#121212]/60'}`}>
                PPT Agent
              </span>
            </button>

            <div className="hidden items-center gap-8 md:flex">
              {navLinks.map((item, index) => (
                <button
                  key={item.href}
                  type="button"
                  onClick={() => scrollToId(item.href)}
                  className={`landing-nav-link text-sm font-medium tracking-normal transition-colors ${
                    scrolled ? 'text-white/80 hover:text-[#AFFF00]' : 'text-[#121212]/80 hover:text-[#121212]'
                  }`}
                  style={{ animationDelay: `${index * 80}ms` }}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={goCreate}
              className="landing-glow hidden rounded-full bg-[#AFFF00] px-6 py-2.5 text-sm font-bold tracking-normal text-[#121212] md:block"
            >
              去登录
            </button>

            <button
              type="button"
              className="p-2 md:hidden"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label={menuOpen ? '关闭菜单' : '打开菜单'}
            >
              {menuOpen ? (
                <X className={scrolled ? 'text-white' : 'text-[#121212]'} />
              ) : (
                <Menu className={scrolled ? 'text-white' : 'text-[#121212]'} />
              )}
            </button>
          </div>

          {menuOpen && (
            <div className="border-t border-white/10 bg-[#121212]/95 px-6 py-4 md:hidden">
              <div className="space-y-3">
                {navLinks.map((item) => (
                  <button
                    key={item.href}
                    type="button"
                    onClick={() => {
                      scrollToId(item.href);
                      setMenuOpen(false);
                    }}
                    className="block w-full py-2 text-left text-lg font-medium text-white/80"
                  >
                    {item.label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={goCreate}
                  className="mt-2 w-full rounded-full bg-[#AFFF00] px-6 py-3 text-sm font-bold text-[#121212]"
                >
                  去登录
                </button>
              </div>
            </div>
          )}
        </nav>

        <section id="hero" className="noise-overlay relative flex min-h-[92svh] items-center overflow-hidden bg-white">
          <div className="absolute inset-0 bg-gradient-to-br from-white via-[#AFFF00]/5 to-white" />
          <div className="landing-orbit landing-orbit-a" />
          <div className="landing-orbit landing-orbit-b" />

          <div className="relative z-10 mx-auto grid max-w-7xl items-center gap-8 px-5 pb-12 pt-28 md:px-6 lg:grid-cols-2">
            <div className="max-w-xl space-y-5">
              <div className="landing-rise inline-flex items-center gap-2 rounded-full bg-[#121212] px-3 py-1.5 font-mono text-xs tracking-normal text-white">
                <span className="h-2 w-2 rounded-full bg-[#AFFF00]" />
                兰台 · PPT AGENT · HARNESS ENGINEERING
              </div>

              <div className="space-y-1">
                <h1 className="landing-hero-line text-4xl font-black leading-[0.95] tracking-normal text-[#121212] sm:text-5xl md:text-7xl">
                  兰台·PPT Agent
                </h1>
                <h1 className="landing-hero-line landing-hero-line-alt text-4xl font-black leading-[0.95] tracking-normal text-[#84cc16] sm:text-5xl md:text-7xl">
                  以 Harness 方式交付
                </h1>
                <p className="landing-rise max-w-md pt-3 text-base leading-relaxed text-[#121212]/70 md:text-lg">
                  不是临时拼页的灵感工具，而是把材料接入、结构编排、风格校验和文件导出串成一条可复盘流水线的 PPT 工程系统。
                </p>
              </div>

              <div className="landing-rise flex flex-wrap gap-3 pt-2">
                <button
                  type="button"
                  onClick={goCreate}
                  className="landing-shine flex items-center gap-2 rounded-full bg-[#AFFF00] px-6 py-3 text-sm font-bold tracking-normal text-[#121212]"
                >
                  开始创建
                  <ArrowRight className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => scrollToId('#formula')}
                  className="rounded-full border-2 border-[#121212] px-6 py-3 text-sm font-bold tracking-normal text-[#121212] transition-colors hover:bg-[#121212] hover:text-white"
                >
                  了解 Harness
                </button>
              </div>

              <div className="landing-rise flex flex-wrap gap-4 pt-2">
                {['材料接入', '结构编排', '风格校验', '稳定交付'].map((benefit) => (
                  <div key={benefit} className="flex items-center gap-2 font-mono text-xs text-[#121212]/60">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#AFFF00]" />
                    {benefit}
                  </div>
                ))}
              </div>
            </div>

            <div className="landing-float relative flex justify-center">
              <div className="absolute inset-0 scale-75 rounded-full bg-lime-500/30 blur-[80px]" />
              <img
                src="/images/hero-flow.png"
                alt="散落的想法、数据与素材逐渐汇聚成有秩序的演示文稿"
                className="relative z-10 w-full max-w-[560px] rounded-2xl border border-[#121212]/10 shadow-2xl"
              />
            </div>
          </div>
        </section>

        <section id="scenarios" className="relative overflow-hidden bg-white py-16">
          <div className={`absolute inset-0 bg-gradient-to-br ${currentScenario.tint}`} />
          <div className="relative z-10 mx-auto max-w-7xl px-5 md:px-6">
            <div className="landing-section-title mb-10 text-center">
              <span className="font-mono text-xs tracking-normal text-[#121212]/60">多场景表达</span>
              <h2 className="mt-2 text-3xl font-black tracking-normal text-[#121212] md:text-5xl">
                不同表达，需要 <span style={{ color: currentScenario.color }}>不同 Harness</span>
              </h2>
            </div>

            <div className="flex items-center justify-center gap-6">
              <button
                type="button"
                onClick={previousScenario}
                className="hidden h-12 w-12 items-center justify-center rounded-full border-2 border-[#121212] transition-colors hover:bg-[#121212] hover:text-white md:flex"
                aria-label="上一个场景"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>

              <div className="landing-scenario w-full max-w-3xl rounded-3xl border-2 border-[#121212]/10 bg-white p-6 shadow-xl md:p-8">
                <div className="grid items-center gap-6 md:grid-cols-2">
                  <div className="relative aspect-[4/3] overflow-hidden rounded-2xl border border-[#121212]/10">
                    <img
                      src={currentScenario.image}
                      alt={`${currentScenario.name}场景示例 PPT`}
                      className="h-full w-full object-cover transition-transform duration-500 hover:scale-105"
                    />
                  </div>

                  <div className="space-y-4">
                    <div>
                      <span className="font-mono text-xs tracking-normal" style={{ color: currentScenario.color }}>
                        {currentScenario.tagline}
                      </span>
                      <h3 className="mt-1 text-3xl font-black tracking-normal text-[#121212] md:text-4xl">
                        {currentScenario.name}
                      </h3>
                    </div>
                    <p className="font-mono text-sm leading-relaxed text-[#121212]/60">{currentScenario.description}</p>
                    <div className="flex flex-wrap gap-2">
                      {currentScenario.badges.map((badge) => (
                        <span key={badge} className="rounded-full bg-[#121212]/5 px-2 py-1 font-mono text-xs text-[#121212]/60">
                          {badge}
                        </span>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={goCreate}
                      className="landing-shine w-full rounded-full px-6 py-3 text-sm font-bold tracking-normal text-[#121212] md:w-auto"
                      style={{ backgroundColor: currentScenario.color }}
                    >
                      生成这种表达
                    </button>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={nextScenario}
                className="hidden h-12 w-12 items-center justify-center rounded-full border-2 border-[#121212] transition-colors hover:bg-[#121212] hover:text-white md:flex"
                aria-label="下一个场景"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-6 flex justify-center gap-4 md:hidden">
              <button type="button" onClick={previousScenario} className="h-10 w-10 rounded-full border-2 border-[#121212]">
                <ChevronLeft className="mx-auto h-4 w-4" />
              </button>
              <button type="button" onClick={nextScenario} className="h-10 w-10 rounded-full border-2 border-[#121212]">
                <ChevronRight className="mx-auto h-4 w-4" />
              </button>
            </div>

            <div className="mt-6 flex justify-center gap-2">
              {scenarios.map((scenario, index) => (
                <button
                  key={scenario.name}
                  type="button"
                  onClick={() => setScenarioIndex(index)}
                  className="h-2 rounded-full transition-all"
                  style={{
                    width: index === scenarioIndex ? 28 : 10,
                    backgroundColor: index === scenarioIndex ? scenario.color : '#12121220',
                  }}
                  aria-label={`切换到${scenario.name}`}
                />
              ))}
            </div>
          </div>
        </section>

        <section id="formula" className="relative overflow-hidden bg-[#121212] py-16">
          <div className="absolute inset-0 bg-gradient-to-b from-[#121212] via-[#0a0a0a] to-[#121212]" />
          <div className="relative z-10 mx-auto max-w-5xl px-5 md:px-6">
            <div className="landing-section-title mb-10 text-center">
              <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#AFFF00]">HARNESS CULTURE</span>
              <h2 className="mt-2 text-3xl font-black tracking-normal text-white md:text-4xl">兰台不是替你拍脑袋，它把表达变成工程</h2>
              <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-white/50 md:text-base">
                你提供内容、意图、参考与判断。系统用接入、编排、校验、交付四个工程环节，把输入转成稳定、可追踪、可继续迭代的页面。
              </p>
              <span className="mx-auto mt-3 block h-[2px] w-12 rounded-full bg-[#AFFF00]" />
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {formula.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div
                    key={item.title}
                    className="landing-formula-card relative overflow-hidden rounded-2xl border border-white/10 bg-[#1a1a1a] p-5"
                    style={{ animationDelay: `${index * 90}ms` }}
                  >
                    <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: `${item.color}20` }}>
                      <Icon className="h-5 w-5" style={{ color: item.color }} />
                    </div>
                    <div className="text-3xl font-black tracking-normal" style={{ color: item.color }}>
                      {item.title}
                    </div>
                    <h3 className="mt-1 text-sm font-semibold text-white">{item.subtitle}</h3>
                    <p className="mt-1 font-mono text-xs text-white/50">{item.description}</p>
                    <span className="mt-4 block h-[2px] rounded-full" style={{ backgroundColor: item.color }} />
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section id="entry" className="relative overflow-hidden bg-white py-16">
          <div className="mx-auto max-w-7xl px-5 md:px-6">
            <div className="landing-section-title mb-10 text-center">
              <span className="font-mono text-xs tracking-normal text-[#121212]/60">使用入口</span>
              <h2 className="mt-2 text-3xl font-black tracking-normal text-[#121212] md:text-5xl">
                从任何 <span className="text-[#AFFF00]">链路起点</span> 开始
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-[#121212]/60">
                一个想法、一段内容、一份旧 PPT、一份你欣赏的参考作品，兰台都会把它们接入 Harness，转化为结构、页面和视觉表达。
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {entries.map((entry) => {
                const Icon = entry.icon;
                return (
                  <button
                    key={entry.title}
                    type="button"
                    onClick={goCreate}
                    className="landing-entry group relative overflow-hidden rounded-2xl bg-[#121212] p-6 text-left transition-transform hover:-translate-y-2"
                  >
                    <div className="absolute inset-0 bg-[#AFFF00] opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                    <div className="relative z-10">
                      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[#AFFF00] transition-colors group-hover:bg-[#121212]">
                        <Icon className="h-5 w-5 text-[#121212] transition-colors group-hover:text-[#AFFF00]" />
                      </div>
                      <h3 className="mb-2 text-lg font-black tracking-normal text-white transition-colors group-hover:text-[#121212]">{entry.title}</h3>
                      <p className="mb-4 font-mono text-xs leading-relaxed text-white/60 transition-colors group-hover:text-[#121212]/60">
                        {entry.description}
                      </p>
                      <span className="flex items-center gap-2 text-xs font-bold tracking-normal text-[#AFFF00] transition-colors group-hover:text-[#121212]">
                        {entry.cta}
                        <ArrowRight className="h-3 w-3" />
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <section id="references" className="relative overflow-hidden bg-[#121212] py-16">
          <div className="mx-auto max-w-7xl px-5 md:px-6">
            <div className="landing-section-title mb-10 text-center">
              <span className="font-mono text-xs tracking-normal text-[#AFFF00]">PPT TO PPT · 参考的意义</span>
              <h2 className="mt-2 text-3xl font-black tracking-normal text-white md:text-5xl">
                优秀作品不是用来 <span className="text-[#AFFF00]">复制的</span>
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-white/50">
                你想借鉴的，往往不是某个背景色，而是它如何组织节奏、铺陈信息。上传参考 PPT，输入你的内容，兰台把参考当成 Harness 约束，再生成属于你的新表达。
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              {references.map((item, index) => (
                <button
                  key={item.image}
                  type="button"
                  onClick={goCreate}
                  className="landing-reference group relative aspect-square overflow-hidden rounded-xl"
                  style={{ animationDelay: `${index * 60}ms` }}
                >
                  <img
                    src={item.image}
                    alt={`参考 PPT 版式示例 ${index + 1}`}
                    className="h-full w-full object-cover grayscale transition-all duration-500 group-hover:scale-105 group-hover:grayscale-0"
                  />
                  <span className="absolute bottom-3 left-3 rounded-full bg-[#121212]/70 px-2 py-1 font-mono text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                    {item.label}
                  </span>
                </button>
              ))}
            </div>

            <div className="mt-8 flex justify-center">
              <button
                type="button"
                onClick={goCreate}
                className="landing-shine flex items-center gap-2 rounded-full bg-[#AFFF00] px-6 py-3 text-sm font-bold tracking-normal text-[#121212]"
              >
                上传参考 PPT
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </section>

        <footer className="relative overflow-hidden bg-[#121212] pb-6 pt-16">
          <div className="relative z-10 mx-auto max-w-7xl px-5 md:px-6">
            <div className="landing-section-title mb-12 text-center">
              <h2 className="text-3xl font-black leading-[1.05] tracking-normal text-white md:text-5xl">
                <span className="block">让每一次 PPT 生产</span>
                <span className="block text-[#AFFF00]">都有工程化交付链</span>
              </h2>
            </div>

            <div className="mx-auto mb-12 max-w-xl">
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="输入你的邮箱，抢先体验"
                  className="w-full rounded-xl border-2 border-white/20 bg-white/5 px-4 py-3 font-mono text-sm text-white placeholder:text-white/40 outline-none transition-colors focus:border-[#AFFF00]"
                />
                <button
                  type="button"
                  onClick={goCreate}
                  className="landing-shine whitespace-nowrap rounded-xl bg-[#AFFF00] px-6 py-3 text-sm font-bold tracking-normal text-[#121212]"
                >
                  开始创建
                </button>
              </div>
              <p className="mt-2 text-center font-mono text-xs text-white/40">从材料到页面，从校验到交付。</p>
            </div>

            <p className="mx-auto mb-10 max-w-xl text-center text-sm leading-relaxed text-white/60">
              兰台·PPT Agent 把复杂内容放入 Harness 工程链路：材料成为结构，结构进入校验，校验后的页面稳定交付。
            </p>

            <div className="grid grid-cols-2 gap-6 border-t border-white/10 py-8 md:grid-cols-4">
              {footerLinks.map((section) => (
                <div key={section.title}>
                  <h4 className="mb-3 text-sm font-bold text-white">{section.title}</h4>
                  <ul className="space-y-2">
                    {section.links.map((link) => (
                      <li key={link}>
                        <button type="button" onClick={goCreate} className="font-mono text-xs text-white/60 transition-colors hover:text-[#AFFF00]">
                          {link}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <div className="flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 md:flex-row">
              <span className="flex items-baseline gap-1.5 text-xl font-black tracking-normal">
                <span className="text-[#AFFF00]">兰台</span>
                <span className="font-mono text-sm text-white/60">PPT Agent</span>
              </span>
              <p className="font-mono text-xs text-white/40">© 2026 兰台·PPT Agent. 保留所有权利。</p>
              <p className="font-mono text-xs text-white/30">Harness your slides</p>
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 select-none text-[15rem] font-black leading-none text-white/[0.02] md:text-[30rem]">
            兰台
          </div>
        </footer>
      </main>
    </ClickSpark>
  );
};
