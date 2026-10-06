import { useRef, useState } from "react";
import { ImagePlus, Plus, UserRound } from "lucide-react";
import type { Binding, Role } from "./api";

type Props = {
  pageId: string;
  roles: Role[];
  bindings: Binding[];
  materials: { id: string; url: string; filename: string }[];
  disabled: boolean;
  onUpload: (file: File, roleId: string) => void;
  onChooseLongTerm?: (roleId: string) => void;
  onRemovePhoto: (roleId: string) => void;
  onSwap: (sourceRole: string, targetRole: string) => void;
  onEdit: (id: string, patch: Partial<Role>) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
};
export function TeamPhotos(props: Props) {
  const input = useRef<HTMLInputElement>(null);
  const targetRole = useRef("");
  const [editing, setEditing] = useState("");
  const [over, setOver] = useState("");
  const photos = props.bindings.filter(
    (b) => b.page_id === props.pageId && b.purpose === "person",
  );
  const choose = (id: string) => {
    targetRole.current = id;
    input.current?.click();
  };
  return (
    <section className="edu-team-photos" aria-label="团队成员照片">
      <header>
        <div>
          <strong>人物参考图</strong>
          <p>上传单人照，或拖动照片到对应成员卡片</p>
        </div>
        <span>
          {photos.length} / {props.roles.length} 已上传 · 最多 12 位
        </span>
      </header>
      <div className="edu-person-grid">
        {props.roles.map((r, i) => {
          const binding = photos.find((b) => b.role_id === r.id);
          const photo = props.materials.find(
            (m) => m.id === binding?.material_id,
          );
          const name = r.member_name || `成员 ${i + 1}`;
          return (
            <article
              key={r.id}
              className={`edu-person-card ${over === r.id ? "drag-over" : ""}`}
              onDragOver={(e) => {
                if (!props.disabled) {
                  e.preventDefault();
                  setOver(r.id);
                }
              }}
              onDragLeave={() => setOver("")}
              onDrop={(e) => {
                e.preventDefault();
                setOver("");
                if (props.disabled) return;
                const file = e.dataTransfer.files[0];
                if (file) {
                  if (file.type.startsWith("image/"))
                    props.onUpload(file, r.id);
                  return;
                }
                const source = e.dataTransfer.getData(
                  "application/x-education-person",
                );
                if (
                  source &&
                  source !== r.id &&
                  props.roles.some((x) => x.id === source)
                )
                  props.onSwap(source, r.id);
              }}
            >
              <button
                className="edu-person-photo"
                aria-label={`${photo ? "更换" : "上传"}${name}照片`}
                disabled={props.disabled}
                onClick={() => choose(r.id)}
                draggable={!!photo && !props.disabled}
                onDragStart={(e) => {
                  e.dataTransfer.setData(
                    "application/x-education-person",
                    r.id,
                  );
                  e.dataTransfer.effectAllowed = "move";
                }}
              >
                {photo ? (
                  <img
                    src={photo.url}
                    alt={`${name}的已上传照片`}
                    draggable={false}
                  />
                ) : (
                  <>
                    <UserRound size={30} />
                    <ImagePlus size={18} />
                    <span>上传单人照</span>
                  </>
                )}
              </button>
              {props.onChooseLongTerm && (
                <button
                  className="edu-library-button"
                  disabled={props.disabled}
                  aria-label={`从长期文件选择${name}照片`}
                  onClick={() => props.onChooseLongTerm?.(r.id)}
                >
                  从长期文件选择
                </button>
              )}
              {editing === r.id ? (
                <div className="edu-person-fields">
                  <input
                    aria-label={`${name}姓名`}
                    placeholder="成员姓名（选填）"
                    value={r.member_name || ""}
                    disabled={props.disabled}
                    onChange={(e) =>
                      props.onEdit(r.id, { member_name: e.target.value })
                    }
                  />
                  <input
                    aria-label={`${name}岗位`}
                    placeholder="岗位名称"
                    value={r.name}
                    disabled={props.disabled}
                    onChange={(e) =>
                      props.onEdit(r.id, { name: e.target.value })
                    }
                  />
                  <button onClick={() => setEditing("")}>完成</button>
                </div>
              ) : (
                <>
                  <strong>{name}</strong>
                  <span className="edu-person-role" title={r.name}>
                    {r.name || "岗位待填写"}
                  </span>
                </>
              )}
              <div className="edu-person-actions">
                <button
                  disabled={props.disabled}
                  onClick={() => setEditing(editing === r.id ? "" : r.id)}
                >
                  编辑
                </button>
                {photo && (
                  <button
                    disabled={props.disabled}
                    onClick={() => props.onRemovePhoto(r.id)}
                  >
                    移除照片
                  </button>
                )}
                <button
                  disabled={props.disabled || props.roles.length <= 1}
                  onClick={() => props.onRemove(r.id)}
                >
                  删除槽位
                </button>
              </div>
            </article>
          );
        })}
        {props.roles.length < 12 && (
          <button
            className="edu-person-add"
            disabled={props.disabled}
            onClick={props.onAdd}
          >
            <Plus size={28} />
            <span>新增人物槽位</span>
          </button>
        )}
      </div>
      <input
        ref={input}
        type="file"
        hidden
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) props.onUpload(file, targetRole.current);
          e.target.value = "";
        }}
      />
      <p className="edu-person-note">
        照片只用于当前团队介绍页。未上传时保留“待补照片”占位；更换照片后，仅本页需要重新生成。
      </p>
    </section>
  );
}
