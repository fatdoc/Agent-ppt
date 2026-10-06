<template>
  <div class="banana-header">
    <span>语义编辑 · 文件保存与导出由主应用管理</span>
    <label v-if="selected?.type === 'image'">替换为已授权素材：
      <select aria-label="替换为已授权素材" @change="replaceAsset(($event.target as HTMLSelectElement).value)">
        <option value="">选择图片</option>
        <option v-for="a in available" :key="a.id" :value="a.url">{{ a.id }}</option>
      </select>
    </label>
    <span role="status">{{ error }}</span>
  </div>
</template>
<script setup lang="ts">
import { computed,inject,ref,type Ref } from 'vue'
import { useSlidesStore,useMainStore,useSnapshotStore } from '@/store'
const slides=useSlidesStore(), main=useMainStore(), snapshots=useSnapshotStore()
const assets=inject<Ref<Record<string,{id:string;url:string}[]>>>('bananaAssets',ref({}))
const selected=computed(()=>slides.currentSlide.elements.find(e=>e.id===main.handleElementId))
const available=computed(()=>assets.value[slides.currentSlide.id] || [])
const error=ref('')
async function replaceAsset(url:string){
  const el=selected.value
  if(!url||el?.type!=='image'||!available.value.some(a=>a.url===url))return
  // Use authorized membership; no arbitrary remote URL or local upload.
  const image=new Image();image.src=url
  try {
    await image.decode()
    const height=el.height,width=height*image.naturalWidth/image.naturalHeight
    if(el.left+width>slides.viewportSize){error.value='图片超出页面，请先缩小或移动';return}
    slides.updateElement({id:el.id,props:{src:url,width,height,clip:{shape:'rect',range:[[0,0],[100,100]]}}})
    snapshots.addSnapshot();error.value='图片已替换，等待主应用保存'
  } catch {error.value='素材加载失败'}
}
</script>
<style scoped>
.banana-header{display:flex;gap:20px;align-items:center;padding:0 16px;font-size:12px}select{border:1px solid #ddd;padding:3px}
</style>
