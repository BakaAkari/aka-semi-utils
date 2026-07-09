import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './HomePage';

export function AppRouter() {
  return (
    <BrowserRouter basename="/tools/watermark">
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </BrowserRouter>
  );
}
