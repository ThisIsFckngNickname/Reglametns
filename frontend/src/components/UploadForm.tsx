import React, { useState, useRef } from 'react';
import { uploadCompanyDocs } from '../api/client';

interface UploadFormProps {
  onUploadResult: (result: { success: boolean; message: string }) => void;
}

export default function UploadForm({ onUploadResult }: UploadFormProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter((f) =>
      f.name.toLowerCase().endsWith('.docx')
    );
    setFiles((prev) => {
      const combined = [...prev, ...droppedFiles].slice(0, 20);
      return combined;
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).filter((f) =>
        f.name.toLowerCase().endsWith('.docx')
      );
      setFiles((prev) => {
        const combined = [...prev, ...selected].slice(0, 20);
        return combined;
      });
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Введите название профиля');
      return;
    }
    if (files.length === 0) {
      setError('Выберите хотя бы один .docx файл');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const response = await uploadCompanyDocs(
        name.trim(),
        files,
        description.trim() || undefined,
      );
      const displayName = response?.name || name.trim();
      const docCount = response?.document_count ?? files.length;

      setName('');
      setDescription('');
      setFiles([]);

      onUploadResult({
        success: true,
        message: `Профиль «${displayName}» успешно создан! Загружено документов: ${docCount}.`,
      });
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(errMsg);
      onUploadResult({
        success: false,
        message: `Ошибка загрузки: ${errMsg}`,
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card upload-form">
      <h2>Загрузка документов</h2>

      <div className="form-group">
        <label htmlFor="profile-name">Название профиля</label>
        <input
          id="profile-name"
          type="text"
          className="input-field"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={uploading}
          placeholder="Например: Регламенты отдела продаж"
        />
      </div>

      <div className="form-group">
        <label htmlFor="profile-desc">Описание (опционально)</label>
        <input
          id="profile-desc"
          type="text"
          className="input-field"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={uploading}
          placeholder="Краткое описание профиля"
        />
      </div>

      <div className="form-group">
        <label>Файлы .docx (1–3)</label>
        <div
          className={`drop-zone${dragOver ? ' active' : ''}${uploading ? ' disabled' : ''}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleFileDrop}
          onClick={() => {
            if (!uploading && fileInputRef.current) {
              fileInputRef.current.click();
            }
          }}
        >
          {files.length === 0 ? (
            <p>Перетащите файлы сюда или нажмите для выбора</p>
          ) : (
            <p>Выбрано файлов: {files.length}/20 (нажмите для добавления)</p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileSelect}
            disabled={uploading}
          />
        </div>
      </div>

      {files.length > 0 && (
        <div className="file-list">
          {files.map((f, idx) => (
            <div key={idx} className="file-item">
              <span className="file-name">{f.name}</span>
              <button
                type="button"
                className="btn btn-small btn-cancel"
                onClick={() => removeFile(idx)}
                disabled={uploading}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      <div className="form-actions">
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={uploading || files.length === 0 || !name.trim()}
        >
          {uploading ? 'Загрузка...' : 'Загрузить'}
        </button>
      </div>
    </div>
  );
}
