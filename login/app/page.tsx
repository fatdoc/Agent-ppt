"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useState } from "react"
import { Eye, EyeOff, User, Lock, Building2, Home } from "lucide-react"

export default function LoginPage() {
  const [activeTab, setActiveTab] = useState<"account" | "code">("account")
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(true)

  return (
    <div className="min-h-screen w-full flex flex-col bg-gradient-to-br from-[#e8f8ee] via-[#f2faf2] to-[#d4f0e0]">
      {/* Top Nav */}
      <header className="w-full flex items-center justify-between px-8 py-4">
        <div className="flex items-center gap-2">
          {/* Brand logo mark */}
          <div className="w-8 h-8 rounded-lg bg-[#4ade80] flex items-center justify-center">
            <span className="text-white font-bold text-sm">兰</span>
          </div>
          <span className="text-[#16a34a] font-semibold text-base tracking-wide">兰台</span>
          <span className="text-gray-400 mx-1">·</span>
          <span className="text-gray-600 text-sm font-medium">PPT Agent</span>
        </div>
        <button className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-[#16a34a] transition-colors">
          <Home className="w-4 h-4" />
          返回首页
        </button>
      </header>

      {/* Main content */}
      <div className="flex-1 flex items-center justify-center p-4 md:p-6 lg:p-8">
        <div className="w-full max-w-[1080px] bg-white rounded-2xl md:rounded-[2rem] shadow-xl overflow-hidden">
          <div className="grid lg:grid-cols-2 gap-0 min-h-[680px]">

            {/* Left Side - Login Form */}
            <div className="flex flex-col items-center justify-center p-8 lg:p-12 bg-white">
              <div className="w-full max-w-[380px] space-y-6">

                {/* Title */}
                <div className="text-center space-y-1">
                  <h1 className="text-2xl font-bold text-gray-900">欢迎登录</h1>
                  <p className="text-sm text-gray-400">
                    登录兰台 PPT Agent，开启智能化 PPT 交付体验
                  </p>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-gray-200">
                  <button
                    onClick={() => setActiveTab("account")}
                    className={`flex-1 pb-2.5 text-sm font-medium transition-colors relative ${
                      activeTab === "account"
                        ? "text-[#16a34a]"
                        : "text-gray-400 hover:text-gray-600"
                    }`}
                  >
                    账号登录
                    {activeTab === "account" && (
                      <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4ade80] rounded-full" />
                    )}
                  </button>
                  <button
                    onClick={() => setActiveTab("code")}
                    className={`flex-1 pb-2.5 text-sm font-medium transition-colors relative ${
                      activeTab === "code"
                        ? "text-[#16a34a]"
                        : "text-gray-400 hover:text-gray-600"
                    }`}
                  >
                    验证码登录
                    {activeTab === "code" && (
                      <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#4ade80] rounded-full" />
                    )}
                  </button>
                </div>

                {/* Form Fields */}
                <div className="space-y-4">
                  {activeTab === "account" ? (
                    <>
                      {/* Username */}
                      <div className="relative">
                        <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <Input
                          type="text"
                          placeholder="请输入账号"
                          defaultValue="admin"
                          className="pl-10 h-[48px] bg-[#f4faf4] border-[#d1fae5] rounded-xl focus-visible:ring-[#4ade80] focus-visible:border-[#4ade80] text-sm"
                        />
                      </div>

                      {/* Password */}
                      <div className="relative">
                        <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <Input
                          type={showPassword ? "text" : "password"}
                          placeholder="请输入密码"
                          defaultValue="password"
                          className="pl-10 pr-10 h-[48px] bg-[#f4faf4] border-[#d1fae5] rounded-xl focus-visible:ring-[#4ade80] focus-visible:border-[#4ade80] text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          {showPassword ? (
                            <Eye className="w-4 h-4" />
                          ) : (
                            <EyeOff className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      {/* Phone */}
                      <div className="relative">
                        <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <Input
                          type="tel"
                          placeholder="请输入手机号"
                          className="pl-10 h-[48px] bg-[#f4faf4] border-[#d1fae5] rounded-xl focus-visible:ring-[#4ade80] focus-visible:border-[#4ade80] text-sm"
                        />
                      </div>

                      {/* Code */}
                      <div className="relative flex gap-2">
                        <Input
                          type="text"
                          placeholder="请输入验证码"
                          className="flex-1 h-[48px] bg-[#f4faf4] border-[#d1fae5] rounded-xl focus-visible:ring-[#4ade80] focus-visible:border-[#4ade80] text-sm"
                        />
                        <button className="h-[48px] px-4 text-sm text-[#16a34a] border border-[#4ade80] rounded-xl hover:bg-[#f0fdf4] transition-colors whitespace-nowrap font-medium">
                          获取验证码
                        </button>
                      </div>
                    </>
                  )}

                  {/* Remember me & Forgot password */}
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <div
                        onClick={() => setRememberMe(!rememberMe)}
                        className={`w-4 h-4 rounded flex items-center justify-center cursor-pointer transition-colors ${
                          rememberMe ? "bg-[#4ade80] border-[#4ade80]" : "border border-gray-300"
                        }`}
                      >
                        {rememberMe && (
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                      <span className="text-sm text-gray-500">记住我</span>
                    </label>
                    <button className="text-sm text-[#16a34a] hover:text-[#4ade80] transition-colors">
                      忘记密码？
                    </button>
                  </div>

                  {/* Login Button */}
                  <Button
                    className="w-full h-[48px] bg-[#4ade80] hover:bg-[#22c55e] text-white font-semibold rounded-xl text-base shadow-sm shadow-green-200 transition-colors"
                  >
                    登录
                  </Button>

                  {/* Register */}
                  <p className="text-center text-sm text-gray-400">
                    还没有账号？{" "}
                    <button className="text-[#16a34a] hover:text-[#4ade80] font-medium transition-colors">
                      注册账号
                    </button>
                  </p>

                  {/* SSO */}
                  <button className="w-full h-[44px] flex items-center justify-center gap-2 border border-gray-200 rounded-xl text-sm text-gray-600 hover:border-[#4ade80] hover:text-[#16a34a] transition-colors bg-white">
                    <Building2 className="w-4 h-4" />
                    企业登录 / SSO
                  </button>

                  {/* Terms */}
                  <p className="text-center text-xs text-gray-400 leading-relaxed">
                    登录即代表您同意{" "}
                    <button className="text-[#16a34a] hover:underline">《用户协议》</button>
                    {" "}与{" "}
                    <button className="text-[#16a34a] hover:underline">《隐私政策》</button>
                  </p>
                </div>
              </div>
            </div>

            {/* Right Side - Image Panel */}
            <div className="relative lg:rounded-[1.5rem] m-0 lg:m-3 overflow-hidden min-h-[320px] lg:min-h-0">
              <img
                src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/ChatGPT%20Image%202026%E5%B9%B46%E6%9C%8827%E6%97%A5%2012_07_12-aLoHosMD9fGIeb5BpzVoLVahTV1qGn.png"
                alt="Harness工程 AI驱动一键生成专业PPT"
                className="absolute inset-0 w-full h-full object-cover object-center"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent" />
              <div className="absolute bottom-6 left-6 right-6">
                <h2 className="text-white text-2xl font-bold leading-tight drop-shadow-lg">
                  Harness工程
                </h2>
                <p className="text-[#4ade80] text-xl font-bold leading-tight drop-shadow-lg">
                  一键生成专业 PPT
                </p>
                <p className="text-white/80 text-sm mt-2 leading-relaxed drop-shadow">
                  AI 驱动 · 智能理解 · 高效输出 · 专业呈现
                </p>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
