export const workspaceStyles = `
  .wm-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .wm-modal {
    background: #1e1e2e;
    color: #cdd6f4;
    border-radius: 8px;
    width: 500px;
    max-width: 90%;
    border: 1px solid #313244;
  }
  .wm-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid #313244;
  }
  .wm-modal-title {
    font-size: 1.25rem;
    font-weight: 600;
  }
  .wm-modal-close {
    background: transparent;
    border: none;
    color: #a6adc8;
    cursor: pointer;
  }
  .wm-modal-tabs {
    display: flex;
    border-bottom: 1px solid #313244;
  }
  .wm-modal-tab {
    flex: 1;
    padding: 12px;
    background: transparent;
    border: none;
    color: #a6adc8;
    cursor: pointer;
    text-align: center;
  }
  .wm-modal-tab-active {
    color: #89b4fa;
    border-bottom: 2px solid #89b4fa;
  }
  .wm-modal-body {
    padding: 16px;
  }
  .wm-modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 16px;
    border-top: 1px solid #313244;
  }
  .wm-btn-cancel {
    padding: 8px 16px;
    background: #313244;
    color: #cdd6f4;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .wm-btn-submit {
    padding: 8px 16px;
    background: #89b4fa;
    color: #11111b;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .wm-btn-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;
