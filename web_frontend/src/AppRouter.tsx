import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './HomePage';
import { DevPage } from './pages/DevPage';

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/_dev" element={<DevPage />} />
      </Routes>
    </BrowserRouter>
  );
}
