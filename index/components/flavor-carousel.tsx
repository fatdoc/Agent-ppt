"use client"

import type React from "react"

import { motion, AnimatePresence, useSpring } from "framer-motion"
import { useState } from "react"
import Image from "next/image"
import { ChevronLeft, ChevronRight } from "lucide-react"

const flavors = [
  {
    id: 1,
    name: "创新创业比赛",
    tagline: "让优势被看见",
    description: "用张力组织节奏，把核心竞争力放在评委一眼能看见的位置。",
    image: "/images/scene-pitch.png",
    bgColor: "from-[#84cc16]/20 via-[#84cc16]/10 to-transparent",
    accentColor: "#84cc16",
    badges: ["竞争力", "节奏张力", "数据论证", "记忆点"],
  },
  {
    id: 2,
    name: "工作汇报",
    tagline: "让进展被理解",
    description: "把复杂进展整理成清晰层级，让结论先行、证据有据可依。",
    image: "/images/scene-report.png",
    bgColor: "from-[#f59e0b]/20 via-[#f59e0b]/10 to-transparent",
    accentColor: "#f59e0b",
    badges: ["结论先行", "清晰层级", "数据可视化", "一致风格"],
  },
  {
    id: 3,
    name: "融资路演",
    tagline: "让判断被相信",
    description: "用笃定的叙事与关键指标，把信念传递给每一位听众。",
    image: "/images/scene-roadshow.png",
    bgColor: "from-[#AFFF00]/20 via-[#AFFF00]/5 to-transparent",
    accentColor: "#AFFF00",
    badges: ["叙事信念", "关键指标", "增长曲线", "强焦点"],
  },
]

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 300 : -300,
    opacity: 0,
    scale: 0.9,
    rotateY: direction > 0 ? 15 : -15,
  }),
  center: {
    x: 0,
    opacity: 1,
    scale: 1,
    rotateY: 0,
    transition: {
      type: "spring",
      stiffness: 300,
      damping: 30,
    },
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -300 : 300,
    opacity: 0,
    scale: 0.9,
    rotateY: direction > 0 ? -15 : 15,
    transition: {
      type: "spring",
      stiffness: 300,
      damping: 30,
    },
  }),
}

export function FlavorCarousel() {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [[page, direction], setPage] = useState([0, 0])
  const currentFlavor = flavors[currentIndex]

  const rotateX = useSpring(0, { stiffness: 150, damping: 20 })
  const rotateY = useSpring(0, { stiffness: 150, damping: 20 })

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    const x = (e.clientX - centerX) / (rect.width / 2)
    const y = (e.clientY - centerY) / (rect.height / 2)
    rotateY.set(x * 5)
    rotateX.set(-y * 5)
  }

  const handleMouseLeave = () => {
    rotateX.set(0)
    rotateY.set(0)
  }

  const paginate = (newDirection: number) => {
    const newIndex = (currentIndex + newDirection + flavors.length) % flavors.length
    setCurrentIndex(newIndex)
    setPage([page + newDirection, newDirection])
  }

  const nextFlavor = () => paginate(1)
  const prevFlavor = () => paginate(-1)

  return (
    <section id="flavours" className="relative py-16 bg-white overflow-hidden">
      <motion.div
        className={`absolute inset-0 bg-gradient-to-br ${currentFlavor.bgColor}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        key={currentFlavor.id}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.25, 0.4, 0.25, 1] }}
          className="text-center mb-10"
        >
          <motion.span
            className="font-mono text-[#121212]/60 text-xs tracking-widest"
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
          >
            多场景表达
          </motion.span>
          <h2 className="text-3xl md:text-5xl font-black text-[#121212] tracking-tighter mt-2 overflow-hidden">
            <motion.span
              className="inline-block"
              initial={{ y: 80 }}
              whileInView={{ y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.25, 0.4, 0.25, 1] }}
            >
              不同表达，需要{" "}
            </motion.span>
            <motion.span
              className="inline-block"
              style={{ color: currentFlavor.accentColor }}
              initial={{ y: 80 }}
              whileInView={{ y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.25, 0.4, 0.25, 1], delay: 0.1 }}
            >
              不同语言
            </motion.span>
          </h2>
        </motion.div>

        {/* Carousel */}
        <div className="relative">
          <div className="flex items-center justify-center gap-6">
            <motion.button
              onClick={prevFlavor}
              className="hidden md:flex w-12 h-12 rounded-full border-2 border-[#121212] items-center justify-center hover:bg-[#121212] hover:text-white transition-colors"
              whileHover={{ scale: 1.1, rotate: -5 }}
              whileTap={{ scale: 0.9 }}
              transition={{ type: "spring", stiffness: 400, damping: 17 }}
            >
              <ChevronLeft className="w-5 h-5" />
            </motion.button>

            <AnimatePresence mode="wait" custom={direction}>
              <motion.div
                key={currentFlavor.id}
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                className="relative w-full max-w-3xl"
                style={{ perspective: 1000 }}
              >
                <motion.div
                  className="bg-white rounded-3xl p-6 md:p-8 border-2 border-[#121212]/10 shadow-xl"
                  style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
                  onMouseMove={handleMouseMove}
                  onMouseLeave={handleMouseLeave}
                >
                  <div className="grid md:grid-cols-2 gap-6 items-center">
                    <motion.div
                      className="relative aspect-[4/3] flex items-center justify-center overflow-hidden rounded-2xl border border-[#121212]/10"
                      whileHover={{ scale: 1.03 }}
                      transition={{ type: "spring", stiffness: 300, damping: 20 }}
                    >
                      <Image
                        src={currentFlavor.image || "/placeholder.svg"}
                        alt={`${currentFlavor.name}场景示例 PPT`}
                        fill
                        className="object-cover"
                      />
                    </motion.div>

                    <div className="space-y-4">
                      <div>
                        <motion.span
                          className="font-mono text-xs tracking-widest"
                          style={{ color: currentFlavor.accentColor }}
                          initial={{ opacity: 0, x: -20 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.2 }}
                        >
                          {currentFlavor.tagline}
                        </motion.span>
                        <motion.h3
                          className="text-3xl md:text-4xl font-black text-[#121212] tracking-tighter mt-1"
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.3, type: "spring", stiffness: 100 }}
                        >
                          {currentFlavor.name}
                        </motion.h3>
                      </div>

                      <motion.p
                        className="text-sm text-[#121212]/60 font-mono"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.4 }}
                      >
                        {currentFlavor.description}
                      </motion.p>

                      <motion.div
                        className="flex flex-wrap gap-2"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.5 }}
                      >
                        {currentFlavor.badges.map((badge) => (
                          <span
                            key={badge}
                            className="px-2 py-1 bg-[#121212]/5 rounded-full text-xs font-mono text-[#121212]/60"
                          >
                            {badge}
                          </span>
                        ))}
                      </motion.div>

                      <motion.button
                        className="px-6 py-3 rounded-full font-bold text-sm tracking-wide w-full md:w-auto relative overflow-hidden"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        transition={{ type: "spring", stiffness: 400, damping: 17 }}
                        style={{ backgroundColor: currentFlavor.accentColor, color: "#121212" }}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                      >
                        <motion.span
                          className="absolute inset-0 bg-white/20"
                          initial={{ x: "-100%" }}
                          whileHover={{ x: "100%" }}
                          transition={{ duration: 0.5 }}
                        />
                        <span className="relative z-10">生成这种表达</span>
                      </motion.button>
                    </div>
                  </div>
                </motion.div>
              </motion.div>
            </AnimatePresence>

            <motion.button
              onClick={nextFlavor}
              className="hidden md:flex w-12 h-12 rounded-full border-2 border-[#121212] items-center justify-center hover:bg-[#121212] hover:text-white transition-colors"
              whileHover={{ scale: 1.1, rotate: 5 }}
              whileTap={{ scale: 0.9 }}
              transition={{ type: "spring", stiffness: 400, damping: 17 }}
            >
              <ChevronRight className="w-5 h-5" />
            </motion.button>
          </div>

          <div className="flex md:hidden justify-center gap-4 mt-6">
            <motion.button
              onClick={prevFlavor}
              className="w-10 h-10 rounded-full border-2 border-[#121212] flex items-center justify-center"
              whileTap={{ scale: 0.9 }}
            >
              <ChevronLeft className="w-4 h-4" />
            </motion.button>
            <motion.button
              onClick={nextFlavor}
              className="w-10 h-10 rounded-full border-2 border-[#121212] flex items-center justify-center"
              whileTap={{ scale: 0.9 }}
            >
              <ChevronRight className="w-4 h-4" />
            </motion.button>
          </div>

          <div className="flex justify-center gap-2 mt-6">
            {flavors.map((flavor, index) => (
              <motion.button
                key={flavor.id}
                onClick={() => {
                  const newDirection = index > currentIndex ? 1 : -1
                  setCurrentIndex(index)
                  setPage([index, newDirection])
                }}
                className="h-2 rounded-full transition-all"
                style={{
                  backgroundColor: index === currentIndex ? flavor.accentColor : "#12121220",
                }}
                animate={{
                  width: index === currentIndex ? 28 : 10,
                }}
                whileHover={{ scale: 1.2 }}
                transition={{ type: "spring", stiffness: 400, damping: 25 }}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
