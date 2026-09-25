<template>
  <div class="bridge-status" role="status">{{ status }} · PPTist · 仅支持已验证的语义能力；不支持的修改会阻止保存</div>
  <Editor v-if="loaded" class="bridge-editor" />
  <div v-else class="bridge-wait">等待 Banana Slides 加载语义文档…</div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick, provide } from 'vue'
import { useSlidesStore, useSnapshotStore } from '@/store'
import Editor from './views/Editor/index.vue'
import type { Slide } from '@/types/slides'
import { message, receive } from '../../shared/pptistProtocol'
const store=useSlidesStore(), snapshots=useSnapshotStore()
const session=new URLSearchParams(location.search).get('session') || ''
const origin=location.origin
const assetOptions=ref<Record<string,{id:string;url:string}[]>>({});provide('bananaAssets',assetOptions)
const loaded=ref(false), status=ref('尚未加载')
let sequence=0, timer: ReturnType<typeof setTimeout> | undefined, composing=false, readyTimer: ReturnType<typeof setInterval> | undefined, loading=false
function send(type: Parameters<typeof message>[1], payload: Record<string,unknown>={}) {
  if(window.parent!==window) window.parent.postMessage(message(session,type,payload),origin)
}
function changed() {
  clearTimeout(timer)
  timer=setTimeout(()=>{
    if (!loaded.value || composing) return
    send('DOCUMENT_CHANGED',{slides:JSON.parse(JSON.stringify(store.slides)),sequence:++sequence})
    status.value='有未保存修改'
  },500)
}
watch(()=>store.slides,changed,{deep:true})
async function onMessage(event: MessageEvent) {
  const m=receive(event,window.parent,session,origin)
  if(!m) return
  if(m.type==='LOAD_DOCUMENT' && !loaded.value && !loading) {
    loading=true;clearInterval(readyTimer)
    assetOptions.value=(m.payload.asset_options || {}) as Record<string,{id:string;url:string}[]>
    store.setViewportSize(m.payload.width as number)
    store.setViewportRatio((m.payload.height as number)/(m.payload.width as number))
    store.setSlides(m.payload.slides as Slide[])
    store.slideIndex=0
    await nextTick(); clearTimeout(timer)
    await snapshots.initSnapshotDatabase()
    loaded.value=true; status.value=m.payload.fixture ? '人工测试样例 · 未保存到项目' : '文档已加载'
  }
  if(m.type==='REQUEST_EXPORT' && loaded.value) { if(composing){send('ERROR',{message:'请完成中文输入后再导出'});return;}document.dispatchEvent(new Event('banana-editor-flush'));await nextTick();clearTimeout(timer);send('DOCUMENT_CHANGED',{slides:JSON.parse(JSON.stringify(store.slides)),sequence:++sequence});send('REQUEST_EXPORT'); }
  if(m.type==='SAVE_RESULT' && m.payload.sequence===sequence) status.value=m.payload.ok ? '服务端已保存' : String(m.payload.message || '保存失败，修改仍保留')
}
function beginComposition(){composing=true}
function endComposition(){composing=false;changed()}
onMounted(()=>{window.addEventListener('message',onMessage);document.addEventListener('compositionstart',beginComposition);document.addEventListener('compositionend',endComposition);send('READY');readyTimer=setInterval(()=>{if(!loaded.value&&!loading)send('READY')},500)})
onUnmounted(()=>{clearInterval(readyTimer);clearTimeout(timer);window.removeEventListener('message',onMessage);document.removeEventListener('compositionstart',beginComposition);document.removeEventListener('compositionend',endComposition)})
</script>
<style lang="scss">
#app { height: 100%; }
.bridge-status {height:28px;padding:4px 14px;box-sizing:border-box;background:#f5f4ef;color:#555;font:12px system-ui}
.bridge-editor {height:calc(100% - 28px)!important}
.bridge-wait {padding:40px;font:16px system-ui}
</style>
