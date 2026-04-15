function FileField({ accept, file, hint, label, onChange }) {
  return (
    <label className="upload-card">
      <input
        accept={accept}
        type="file"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      <div className="upload-card-header">
        <div>
          <p className="upload-card-title">{label}</p>
          <p className="upload-card-hint">{hint}</p>
        </div>
        <span className={`file-state ${file ? '' : 'is-empty'}`}>
          {file ? '已选择' : '待上传'}
        </span>
      </div>
      <p className="upload-card-name">{file ? file.name : '点击选择文件'}</p>
    </label>
  )
}

export default FileField
