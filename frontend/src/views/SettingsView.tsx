import { ChangeEvent, useEffect, useState } from "react";
import { ArrowLeft, LogOut, RotateCcw, Save, Upload } from "lucide-react";
import * as api from "../api/client";
import type { ExamLevel, UserProfile } from "../types";
import { AVATAR_COLORS } from "../utils/format";

interface SettingsViewProps {
  profile: UserProfile | null;
  onProfileUpdated: (profile: UserProfile) => void;
  onBackHome: () => void;
  onLogout: () => void;
  onRequireLogin: () => void;
  onToast: (text: string, type?: "info" | "success" | "error") => void;
}

export function SettingsView({
  profile,
  onProfileUpdated,
  onBackHome,
  onLogout,
  onRequireLogin,
  onToast,
}: SettingsViewProps) {
  const [displayName, setDisplayName] = useState("");
  const [avatarColor, setAvatarColor] = useState("#4285f4");
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [examLevel, setExamLevel] = useState<"" | ExamLevel>("");
  const [year, setYear] = useState("");
  const [month, setMonth] = useState("");
  const [day, setDay] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!profile) return;
    setDisplayName(profile.display_name || "");
    setAvatarColor(profile.avatar_color || "#4285f4");
    setAvatarUrl(profile.avatar_url || null);
    setExamLevel(profile.exam_level || "");
    if (profile.exam_date) {
      const [y, m, d] = profile.exam_date.split("-");
      setYear(String(parseInt(y, 10) || ""));
      const mNum = parseInt(m, 10);
      setMonth(mNum === 6 || mNum === 12 ? String(mNum) : "");
      setDay(String(parseInt(d, 10) || ""));
    } else {
      setYear("");
      setMonth("");
      setDay("");
    }
  }, [profile]);

  if (!profile) {
    return (
      <div className="page-container" style={{ maxWidth: 640 }}>
        <div className="m3-card" style={{ textAlign: "center", padding: 36 }}>
          <h2 style={{ marginTop: 0 }}>尚未登录</h2>
          <p style={{ color: "var(--md-sys-color-on-surface-variant)" }}>
            登录后即可自定义头像、昵称与四六级考试倒计时。
          </p>
          <button type="button" className="m3-btn-filled" onClick={onRequireLogin}>
            前往登录 / 注册
          </button>
        </div>
      </div>
    );
  }

  const handleAvatarUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      const res = await api.uploadAvatar(file);
      setAvatarUrl(res.avatar_url);
      onProfileUpdated({ ...profile, avatar_url: res.avatar_url });
      onToast("头像上传成功", "success");
    } catch (err) {
      onToast(err instanceof Error ? err.message : "上传失败", "error");
    }
  };

  const handleAvatarReset = async () => {
    try {
      await api.deleteAvatar();
      setAvatarUrl(null);
      onProfileUpdated({ ...profile, avatar_url: null });
      onToast("已重置为字母头像", "info");
    } catch (err) {
      onToast(err instanceof Error ? err.message : "重置失败", "error");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    let examDatePayload: string | null | undefined = undefined;
    const y = year.trim();
    const m = month.trim();
    const d = day.trim();
    if (y && m && d) {
      examDatePayload = `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
    } else if (!y && !m && !d) {
      examDatePayload = null;
    }

    try {
      await api.updateProfile({
        display_name: displayName.trim() || null,
        avatar_color: avatarColor,
        exam_level: examLevel || null,
        ...(examDatePayload !== undefined ? { exam_date: examDatePayload } : {}),
      });
      const fresh = await api.getProfile();
      onProfileUpdated(fresh);
      onToast("个人设置已保存", "success");
    } catch (err) {
      onToast(err instanceof Error ? err.message : "保存失败", "error");
    } finally {
      setSaving(false);
    }
  };

  const initial = (displayName.trim() || profile.username).charAt(0).toUpperCase();

  return (
    <div className="page-container" style={{ maxWidth: 760 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ margin: "0 0 4px", fontSize: 24 }}>偏好设置与账户</h1>
          <p style={{ margin: 0, fontSize: 13, color: "var(--md-sys-color-on-surface-variant)" }}>
            账号：{profile.username} · 角色：{profile.role === "admin" ? "管理员" : "学生"}
          </p>
        </div>
        <button type="button" className="m3-btn-outlined m3-btn-sm" onClick={onLogout}>
          <LogOut size={14} />
          <span>退出登录</span>
        </button>
      </div>

      <section className="m3-card" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>个人信息</h2>

        <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
          <div
            className="avatar-circle"
            style={{
              width: 68,
              height: 68,
              fontSize: 26,
              ...(avatarUrl
                ? { backgroundImage: `url(${avatarUrl})` }
                : { backgroundColor: avatarColor }),
            }}
          >
            {!avatarUrl ? initial : null}
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <label className="m3-btn-tonal m3-btn-sm" style={{ cursor: "pointer" }}>
              <Upload size={14} />
              <span>上传图片</span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                hidden
                onChange={handleAvatarUpload}
              />
            </label>
            <button
              type="button"
              className="m3-btn-outlined m3-btn-sm"
              onClick={handleAvatarReset}
            >
              <RotateCcw size={14} />
              <span>重置头像</span>
            </button>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>头像底色</div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {AVATAR_COLORS.map((color) => (
              <button
                key={color}
                type="button"
                className={`color-swatch ${avatarColor === color ? "selected" : ""}`}
                style={{ backgroundColor: color }}
                onClick={() => setAvatarColor(color)}
                title={color}
              />
            ))}
          </div>
        </div>

        <label style={{ fontSize: 13, fontWeight: 600 }}>
          昵称（最多 30 字）
          <input
            className="m3-input"
            style={{ marginTop: 6 }}
            maxLength={30}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="输入你的昵称"
          />
        </label>
      </section>

      <section className="m3-card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>考试信息</h2>

        <label style={{ fontSize: 13, fontWeight: 600 }}>
          备考级别
          <select
            className="m3-select"
            style={{ marginTop: 6 }}
            value={examLevel}
            onChange={(e) => setExamLevel(e.target.value as "" | ExamLevel)}
          >
            <option value="">未选择</option>
            <option value="CET4">CET4（英语四级）</option>
            <option value="CET6">CET6（英语六级）</option>
          </select>
        </label>

        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
            目标考试日期（CET 每年 6 月与 12 月举办）
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
            <input
              className="m3-input"
              type="number"
              min={2024}
              max={2099}
              placeholder="年 (如 2026)"
              value={year}
              onChange={(e) => setYear(e.target.value)}
            />
            <select
              className="m3-select"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            >
              <option value="">月份</option>
              <option value="6">6 月</option>
              <option value="12">12 月</option>
            </select>
            <input
              className="m3-input"
              type="number"
              min={1}
              max={31}
              placeholder="日 (如 14)"
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
          </div>
        </div>
      </section>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button type="button" className="m3-btn-outlined" onClick={onBackHome}>
          <ArrowLeft size={16} />
          <span>返回首页</span>
        </button>

        <button
          type="button"
          className="m3-btn-filled"
          disabled={saving}
          onClick={handleSave}
        >
          <Save size={16} />
          <span>{saving ? "保存中..." : "保存设置"}</span>
        </button>
      </div>
    </div>
  );
}
