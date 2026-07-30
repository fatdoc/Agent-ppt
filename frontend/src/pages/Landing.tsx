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
const APP_EDITION = import.meta.env.VITE_APP_EDITION || '职业教育版';

const navLinks = [
  { label: '首页', href: '#hero' },
  { label: '理念', href: '#formula' },
  { label: '场景', href: '#scenarios' },
  { label: '参考', href: '#references' },
  { label: '入口', href: '#entry' },
];

const scenarios = [
  {
    name: '创新创业比赛',
    tagline: '让优势被看见',
    description: '用张力组织节奏，把核心竞争力放在评委一眼能看见的位置。',
    image: '/images/scene-pitch.png',
    color: '#84cc16',
    tint: 'from-lime-400/20 via-lime-400/10 to-transparent',
    badges: ['竞争力', '节奏张力', '数据论证', '记忆点'],
  },
  {
    name: '工作汇报',
    tagline: '让进展被理解',
    description: '把复杂进展整理成清晰层级，让结论先行、证据有据可依。',
    image: '/images/scene-report.png',
    color: '#f59e0b',
    tint: 'from-amber-400/20 via-amber-400/10 to-transparent',
    badges: ['结论先行', '清晰层级', '数据可视化', '一致风格'],
  },
  {
    name: '融资路演',
    tagline: '让判断被相信',
    description: '用笃定的叙事与关键指标，把信念传递给每一位听众。',
    image: '/images/scene-roadshow.png',
    color: accent,
    tint: 'from-[#AFFF00]/20 via-[#AFFF00]/5 to-transparent',
    badges: ['叙事信念', '关键指标', '增长曲线', '强焦点'],
  },
];

const formula = [
  {
    icon: Layers,
    title: '结构',
    subtitle: '理解与重组',
    description: '梳理论点、证据与结论的顺序',
    color: accent,
  },
  {
    icon: Type,
    title: '风格',
    subtitle: '语气与节奏',
    description: '为不同场景匹配表达语言',
    color: '#FF6B35',
  },
  {
    icon: ImageIcon,
    title: '视觉',
    subtitle: '层级与留白',
    description: '让信息有重量，焦点有秩序',
    color: '#00D4FF',
  },
  {
    icon: FileOutput,
    title: '导出',
    subtitle: '稳定可展示',
    description: '生成一组可直接使用的页面',
    color: accent,
  },
];

const entries = [
  {
    icon: Wand2,
    title: '精准生成',
    description: '面向世界职业院校技能大赛/争夺赛，把项目资料整理成可编辑的现场展示作战稿。',
    cta: '进入精准生成',
    path: '/ppt-editor',
  },
  {
    icon: Wand2,
    title: '快速开始',
    description: '从一个主题开始，无需思考结构，直接得到完整初稿。',
    cta: '从主题开始',
  },
  {
    icon: FileText,
    title: '从内容生成',
    description: '把材料、数据与文字交给系统，转化为页面与视觉。',
    cta: '从内容开始',
  },
  {
    icon: Copy,
    title: '借鉴优秀 PPT',
    description: '上传参考作品，学习它的结构、语气与视觉语言。',
    cta: '从参考开始',
  },
  {
    icon: RefreshCw,
    title: 'PPT 翻新',
    description: '让旧稿重新获得秩序，焕发清晰而有力的表达。',
    cta: '从旧稿开始',
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
  { title: '入口', links: ['精准生成', '快速开始', '从内容生成', '借鉴优秀 PPT', 'PPT 翻新'] },
  { title: '场景', links: ['创新创业比赛', '工作汇报', '教学课件', '融资路演'] },
  { title: '关于', links: ['产品理念', '更新日志', '加入我们', '联系我们'] },
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
              <span className="text-[#AFFF00]">启发</span>
              <span className={`font-mono text-sm ${scrolled ? 'text-white/70' : 'text-[#121212]/60'}`}>
                {APP_EDITION}
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
              开始创建
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
                  开始创建
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
                启发 · BANANA SLIDES
              </div>

              <div className="space-y-1">
                <h1 className="landing-hero-line text-4xl font-black leading-[0.95] tracking-normal text-[#121212] sm:text-5xl md:text-7xl">
                  每一次表达
                </h1>
                <h1 className="landing-hero-line landing-hero-line-alt text-4xl font-black leading-[0.95] tracking-normal text-[#84cc16] sm:text-5xl md:text-7xl">
                  都始于混沌
                </h1>
                <p className="landing-rise max-w-md pt-3 text-base leading-relaxed text-[#121212]/70 md:text-lg">
                  想法、材料、数据、截图、旧文件散落各处。真正困难的，不是打开 PPT，而是让它们形成可以被理解、被相信、被记住的秩序。
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
                  了解理念
                </button>
              </div>

              <div className="landing-rise flex flex-wrap gap-4 pt-2">
                {['结构化', '视觉化', '多场景', '参考生成'].map((benefit) => (
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
                不同表达，需要 <span style={{ color: currentScenario.color }}>不同语言</span>
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
              <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#AFFF00]">系统的角色</span>
              <h2 className="mt-2 text-3xl font-black tracking-normal text-white md:text-4xl">启发不是替你表达，它帮助表达成形</h2>
              <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-white/50 md:text-base">
                你提供内容、意图、参考与判断。系统负责理解、重组、视觉化与生成，输入经过四层转换，成为一组稳定的页面。
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
                从任何 <span className="text-[#AFFF00]">起点开始</span>
              </h2>
              <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-[#121212]/60">
                一个想法、一段内容、一份旧 PPT、一份你欣赏的参考作品，启发都会把它们转化为结构、页面和视觉表达。
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
              {entries.map((entry) => {
                const Icon = entry.icon;
                return (
                  <button
                    key={entry.title}
                    type="button"
                    onClick={() => navigate(entry.path || '/app')}
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
                你想借鉴的，往往不是某个背景色，而是它如何组织节奏、铺陈信息。上传参考 PPT，输入你的内容，启发学习它的结构、语气与视觉语言，再生成属于你的新表达。
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
                <span className="block">让你的想法</span>
                <span className="block text-[#AFFF00]">抵达它应有的形式</span>
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
              <p className="mt-2 text-center font-mono text-xs text-white/40">从混沌到秩序，从秩序到说服。</p>
            </div>

            <p className="mx-auto mb-10 max-w-xl text-center text-sm leading-relaxed text-white/60">
              启发 {APP_EDITION} 把复杂内容生成清晰、有力、可展示的演示文稿。让材料成为结构，让结构成为叙事，让叙事成为画面。
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
                <span className="text-[#AFFF00]">启发</span>
                <span className="font-mono text-sm text-white/60">{APP_EDITION}</span>
              </span>
              <p className="font-mono text-xs text-white/40">© 2026 启发 {APP_EDITION}. 保留所有权利。</p>
              <p className="font-mono text-xs text-white/30">从混沌到秩序</p>
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 select-none text-[15rem] font-black leading-none text-white/[0.02] md:text-[30rem]">
            启发
          </div>
        </footer>
      </main>
    </ClickSpark>
  );
};
