import { useCallback, useEffect, useRef, useState } from 'react';

interface PasswordGateProps {
  onSuccess: () => void;
}

export function PasswordGate({ onSuccess }: PasswordGateProps) {
  const [value, setValue] = useState('');
  const [error, setError] = useState(false);
  const [shaking, setShaking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const check = useCallback((pw: string) => {
    if (pw === '23323312') {
      sessionStorage.setItem('_dev_auth', 'true');
      setError(false);
      onSuccess();
    } else {
      setError(true);
      setShaking(true);
      setTimeout(() => setShaking(false), 400);
    }
  }, [onSuccess]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      check(value);
    }
  };

  return (
    <div className="dev-password-gate">
      <div className={`dev-password-box ${shaking ? 'shake' : ''} ${error ? 'error' : ''}`}>
        <div className="dev-password-title">开发者面板</div>
        <input
          ref={inputRef}
          className="dev-password-input"
          type="password"
          placeholder="输入密码"
          value={value}
          onChange={e => { setValue(e.target.value); setError(false); }}
          onKeyDown={handleKeyDown}
        />
        {error && <div className="dev-password-error">密码错误</div>}
      </div>
    </div>
  );
}
