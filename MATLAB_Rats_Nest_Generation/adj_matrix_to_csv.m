

forces = readforce('dump.matlab.force0');      % Load the force data
positions = readpos('dump.matlab.position0');     % Load the position data

adj = adjmatrix(forces, positions);    % Compute adjacency matrix

adj(adj ~= 0) = 1; % Makes all non-zero values 1s

csvwrite('pos.csv', positions)
writematrix(adj, 'adj.csv');  % Export to CSV if needed