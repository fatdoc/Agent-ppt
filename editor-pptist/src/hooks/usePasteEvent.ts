import { onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore } from '@/store'
import usePasteTextClipboardData from './usePasteTextClipboardData'
import usePasteDataTransfer from './usePasteDataTransfer'

export default () => {
  const { editorAreaFocus, thumbnailsFocus, disableHotkeys } = storeToRefs(useMainStore())

  const { pasteTextClipboardData } = usePasteTextClipboardData()
  const { pasteDataTransfer } = usePasteDataTransfer()

  /**
   * 粘贴事件监听
   * @param e ClipboardEvent
   */
  const pasteListener = (e: ClipboardEvent) => {
    if (!editorAreaFocus.value && !thumbnailsFocus.value) return
    if (disableHotkeys.value) return

    // Only text inside ProseMirror is supported; no object JSON/new slides.
    e.preventDefault()

  }

  onMounted(() => {
    document.addEventListener('paste', pasteListener)
  })
  onUnmounted(() => {
    document.removeEventListener('paste', pasteListener)
  })
}