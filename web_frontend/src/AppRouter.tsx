import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { API_BASE } from './env';
import { HomePage } from './HomePage';

export function AppRouter() {
  return (
    <BrowserRouter basename={API_BASE}>
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </BrowserRouter>
  );
}
