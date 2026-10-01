import { PageConfig, URLExt } from '@jupyterlab/coreutils';

const plugin = {
  id: '@course/stop-tpu-server:plugin',
  autoStart: true,
  activate: app => {
    const hubPrefix = PageConfig.getOption('hubPrefix');
    const hubHost = PageConfig.getOption('hubHost');
    const viewer = PageConfig.getOption('hubUser');
    const username = PageConfig.getOption('hubServerUser');
    const serverName = PageConfig.getOption('hubServerName');

    if (!hubPrefix || !username) {
      return;
    }

    app.commands.addCommand('course:stop-tpu-server', {
      label: 'Stop TPU Server',
      caption: 'Stop this server and return to Hub home',
      isEnabled: () => viewer === username,
      execute: async () => {
        if (viewer !== username) {
          return;
        }
        if (!window.confirm('Save your work before stopping the TPU server. Stop now?')) {
          return;
        }

        const token = PageConfig.getToken();
        if (!token) {
          window.alert('Could not stop the TPU server: missing Hub login token.');
          return;
        }

        const userPath = URLExt.join(
          hubPrefix,
          'api',
          'users',
          encodeURIComponent(username)
        );
        const apiPath = serverName
          ? URLExt.join(userPath, 'servers', encodeURIComponent(serverName))
          : URLExt.join(userPath, 'server');

        try {
          const response = await fetch(hubHost + apiPath, {
            method: 'DELETE',
            headers: { Authorization: `token ${token}` },
            credentials: 'same-origin'
          });

          if (response.status !== 202 && response.status !== 204) {
            throw new Error(`Hub returned HTTP ${response.status}`);
          }

          window.location.assign(hubHost + URLExt.join(hubPrefix, 'home'));
        } catch (error) {
          window.alert(`Could not stop the TPU server: ${error.message}`);
        }
      }
    });
  }
};

export default plugin;
