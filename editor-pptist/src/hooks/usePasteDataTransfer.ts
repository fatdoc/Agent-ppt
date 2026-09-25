// Banana Slides owns document initialization and authorized assets.
// Drop/paste of PPTX/private JSON/media is intentionally unsupported in MVP.
export default () => ({
  pasteDataTransfer(dataTransfer: DataTransfer) {
    return { isFile: true, dataTransferFirstItem: dataTransfer.items[0] }
  },
})
