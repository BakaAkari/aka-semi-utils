import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { API_BASE } from './env';
import { HomePage } from './HomePage';
import { V3HomePage } from './V3HomePage';

export function AppRouter() {
  return (
    <BrowserRouter basename={API_BASE}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/v3" element={<V3HomePage />} />
      </Routes>
    </BrowserRouter>
  );
}
